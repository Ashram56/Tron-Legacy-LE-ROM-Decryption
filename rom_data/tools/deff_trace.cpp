// deff_trace: run trn_174h in libpinmame (ARM hook build) and log every text draw, image draw,
// frame flip, deff start and RNG call, while forcing display effects during a running game.
// Based on mpf_package/tools/tracer.cpp (call injection through the task_sleep 0xb91c hijack).
//
// Build: g++ -O2 -std=c++17 -I/home/claude/pinmame/src/libpinmame deff_trace.cpp -L/home/claude/pinmame/build
//        -lpinmame -lpthread -Wl,-rpath,/home/claude/pinmame/build -o deff_trace
// Run:   PINMAME_NOJIT=1 ./deff_trace LOG MODE [options] ITEMS...
//   MODE force : ITEMS are deffs to force one after another, each "ID" or "ID:w30:w34:w38:w3c"
//                (hex or dec words written to the deff task block +0x30.. right after deff_start returns)
//   MODE play  : ITEMS[0] = seed, ITEMS[1] = emulated seconds of random play (tracer.cpp play mode ball sim)
//   options    : -rng CALLER=V1,V2,..  force the result of random_below/random_percent when called from CALLER
//                                     (return address, hex): call k gets Vk (the last value repeats), e.g. -rng 0x10209dc=0,1,2,3
//                -poke ADDR=VALUE[:SIZE] RAM write before each forced deff (e.g. mode state)
//                -hold SEC           max seconds per forced deff (default 12)
//                -nogame             force in attract mode (no game started)
// Log lines: "<t> <EV> key=value ..." (one event per line).
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <thread>
#include <chrono>
#include <vector>
#include <map>
#include <atomic>
#include "libpinmame.h"
extern "C" {
void PinmameSetArmHook(void (*h)(unsigned int, unsigned int*));
unsigned int PinmameArmRead32(unsigned int a);
unsigned int PinmameArmRead8(unsigned int a);
void PinmameArmWrite32(unsigned int a, unsigned int d);
void PinmameArmWrite8(unsigned int a, unsigned int d);
double PinmameEmuTime();
}
static FILE* LOG;
struct Force { int id; std::vector<unsigned> words; };
static std::vector<Force> force; static size_t forceIdx = 0; static std::atomic<int> forceArmed{0};
static double nextForce = 0, forceT = 0, holdSec = 12.0; static int curForce = -1; static int injecting = 0;
static unsigned sv[16]; static int curForceIdx = -1;
static std::map<unsigned, std::vector<unsigned>> rngForce; static std::map<unsigned, size_t> rngPos;
struct Poke { unsigned a, v, sz; }; static std::vector<Poke> pokes;
static unsigned lastActive = 0xffff;

static unsigned r8(unsigned a) { return PinmameArmRead8(a); }
static unsigned r16(unsigned a) { return r8(a) | (r8(a + 1) << 8); }
static unsigned r32(unsigned a) { return PinmameArmRead32(a); }
static std::string rstr(unsigned a, int max = 160) {
  std::string s; if (!a) return s;
  for (int i = 0; i < max; i++) { unsigned c = r8(a + i); if (!c) break; if (c == '"' || c == '\\') s += '\\'; s += (c >= 32 && c < 127) ? (char)c : '?'; }
  return s;
}
static void ctx(unsigned& task, unsigned& tid, unsigned& deff) {
  task = r32(0x372c0); tid = task ? r16(task) : 0; deff = task ? r16(task + 0x24) : 0;
}
static const unsigned TEXT_APIS[] = {0x28ca8, 0x28d08, 0x28d5c, 0x28dd8, 0x28e48, 0x28eb0, 0x28f34, 0x29174, 0x29178,
                                     0x291e4, 0x291e8, 0x29248, 0x29384, 0x29388};
static bool isText(unsigned pc) { for (unsigned a : TEXT_APIS) if (a == pc) return true; return false; }

static void hook(unsigned pc, unsigned* r) {
  double t = PinmameEmuTime();
  if (curForce >= 0 && !injecting && (pc == 0x27830 || pc == 0xb91c)) {
    unsigned act = r16(0x381a8);
    if ((t - forceT > 0.3 && act != (unsigned)curForce) || t - forceT > holdSec) {
      fprintf(LOG, "%.4f FORCE_END id=%d active=%u\n", t, curForce, act); curForce = -1; nextForce = t + 1.0;
    }
  }
  if (isText(pc)) {
    unsigned task, tid, deff; ctx(task, tid, deff); unsigned sp = r[13];
    fprintf(LOG, "%.4f TXT api=%x lr=%x tid=%u deff=%u active=%u r0=%x r1=%x r2=%x r3=%x ip=%x s=", t, pc, r[14], tid, deff,
            r16(0x381a8), r[0], r[1], r[2], r[3], r[12]);
    for (int k = 0; k < 10; k++) fprintf(LOG, "%s%x", k ? "," : "", r32(sp + 4 * k));
    fprintf(LOG, "\n");
    return;
  }
  switch (pc) {
  case 0x28f74: { unsigned sp = r[13];
    fprintf(LOG, "%.4f STR lr=%x font=%u flags=%u x=%d y=%d color=%x buf=%x str=\"%s\"\n", t, r[14], r[2], r[3] & 0xff,
            (int)r32(sp), (int)r32(sp + 4), r32(sp + 8), r[1], rstr(r[0]).c_str()); break; }
  case 0x2928c: { unsigned sp = r[13];
    fprintf(LOG, "%.4f FIT lr=%x list=%x fonts=", t, r[14], r[2]);
    for (int k = 0; k < 12; k++) { unsigned f = r32(r[2] + 4 * k); fprintf(LOG, "%s%u", k ? "," : "", f); if (!f) break; }
    fprintf(LOG, " flags=%u x=%d y=%d maxw=%d str=\"%s\"\n", r[3] & 0xff, (int)r32(sp), (int)r32(sp + 4), (int)r32(sp + 12), rstr(r[0]).c_str());
    break; }
  case 0x28c1c: case 0x28c6c: fprintf(LOG, "%.4f FONTPICK fn=%x lr=%x a0=%x list=%x maxw=%u\n", t, pc, r[14], r[0], r[1], r[2]); break;
  case 0x28c68: case 0x28ca0: fprintf(LOG, "%.4f FONTPICK_RET pc=%x font=%u\n", t, pc, r32(r[4])); break;
  case 0xc6b4: case 0xc6d4: fprintf(LOG, "%.4f RNG_CALL fn=%x lr=%x arg=%u state=%x\n", t, pc, r[14], r[0], r32(0x372c4)); break;
  case 0xc6d0: case 0xc704: {
    unsigned caller = r32(r[13] + 4); unsigned res = r[0];
    auto it = rngForce.find(caller);
    if (it != rngForce.end()) { size_t& p = rngPos[caller]; r[0] = it->second[p < it->second.size() ? p : it->second.size() - 1]; p++; }
    unsigned task, tid, deff; ctx(task, tid, deff);
    fprintf(LOG, "%.4f RNG fn=%x caller=%x result=%u forced=%d final=%u deff=%u active=%u\n", t, pc == 0xc6d0 ? 0xc6b4 : 0xc6d4,
            caller, res, it != rngForce.end(), r[0], deff, r16(0x381a8));
    break; }
  case 0xc708: fprintf(LOG, "%.4f RNG_BAG lr=%x bag=%x\n", t, r[14], r[0]); break;
  case 0x27b94: fprintf(LOG, "%.4f DEFF_START id=%u queue=%u force=%u lr=%x\n", t, r[0], r[1], r[2], r[14]); break;
  case 0x2b378: case 0x2b424: { unsigned task, tid, deff; ctx(task, tid, deff);
    fprintf(LOG, "%.4f IMG api=%x img=%u page=%u x=%d y=%d pal=%x lr=%x deff=%u\n", t, pc, r[0], r[1], (int)r[2], (int)r[3], r32(r[13]), r[14], deff); break; }
  case 0x1023edc: case 0x1023fe4: { unsigned task, tid, deff; ctx(task, tid, deff);
    fprintf(LOG, "%.4f ANIM api=%x first=%u last=%u tpf=%u loops=%u cues=%x lr=%x deff=%u\n", t, pc, r[0], r[1], r[2], r[3], r32(r[13]), r[14], deff); break; }
  case 0x27830: { unsigned task, tid, deff; ctx(task, tid, deff); unsigned act = r16(0x381a8);
    if (act != lastActive) { fprintf(LOG, "%.4f ACTIVE id=%u\n", t, act); lastActive = act; }
    if (tid == 2) fprintf(LOG, "%.4f SHOW deff=%u lr=%x\n", t, deff, r[14]);
    break; }
  case 0xb91c: {
    unsigned task, tid, deff; ctx(task, tid, deff);
    if (injecting) {
      if (r[13] == sv[13]) {
        unsigned tb = r[0];
        if (tb && curForceIdx >= 0) {
          auto& w = force[curForceIdx].words;
          for (size_t k = 0; k < w.size(); k++) PinmameArmWrite32(tb + 0x30 + 4 * k, w[k]);
        }
        for (int i = 0; i < 4; i++) r[i] = sv[i]; r[14] = sv[14]; injecting = 0;
        fprintf(LOG, "%.4f INJECT_RET task=%x\n", t, tb);
      }
      break;
    }
    if (tid == 2 && deff) fprintf(LOG, "%.4f SLEEP deff=%u ticks=%u lr=%x\n", t, deff, r[0], r[14]);
    if (forceArmed && forceIdx < force.size() && curForce < 0 && t > nextForce) {
      curForceIdx = (int)forceIdx; curForce = force[forceIdx++].id; forceT = t;
      for (auto& p : pokes) { if (p.sz == 1) PinmameArmWrite8(p.a, p.v); else PinmameArmWrite32(p.a, p.v); }
      for (int i = 0; i < 16; i++) sv[i] = r[i];
      r[0] = curForce; r[1] = 0; r[2] = 1; r[14] = 0xb91c; r[15] = 0x280b0; injecting = 1;
      fprintf(LOG, "%.4f FORCE id=%d idx=%d w=", t, curForce, curForceIdx);
      for (size_t k = 0; k < force[curForceIdx].words.size(); k++) fprintf(LOG, "%s%x", k ? "," : "", force[curForceIdx].words[k]);
      fprintf(LOG, "\n");
    }
    break; }
  case 0x2c744: fprintf(LOG, "%.4f SND call=%x lr=%x active=%u\n", t, r[0], r[14], r16(0x381a8)); break;
  case 0x101b824: fprintf(LOG, "%.4f TUBE id=%u lr=%x\n", t, r[0], r[14]); break;
  case 0x87ac: fprintf(LOG, "%.4f LEFF id=%u lr=%x\n", t, r[0], r[14]); break;
  }
}
void PINMAMECALLBACK OnDisplayAvailable(int, int, PinmameDisplayLayout*, void*) {}
void PINMAMECALLBACK OnDisplayUpdated(int, void*, PinmameDisplayLayout*, void*) {}
static std::atomic<int> keys[128];
int PINMAMECALLBACK IsKeyPressed(PINMAME_KEYCODE k, void*) { return (int)k < 128 ? keys[(int)k].load() : 0; }
void PINMAMECALLBACK OnState(int, void*) {}
void PINMAMECALLBACK OnLog(PINMAME_LOG_LEVEL l, const char* f, va_list a, void*) { if (l == PINMAME_LOG_LEVEL_ERROR) { vfprintf(stderr, f, a); fprintf(stderr, "\n"); } }
static std::atomic<int> sol[64];
void PINMAMECALLBACK OnSol(PinmameSolenoidState*, void*) {}
static double emu() { return PinmameEmuTime(); }
static void waitemu(double t) { while (emu() < t) std::this_thread::sleep_for(std::chrono::milliseconds(2)); }

int main(int argc, char** argv) {
  if (argc < 3) { fprintf(stderr, "usage: deff_trace LOG force|play [opts] items...\n"); return 1; }
  LOG = fopen(argv[1], "w"); const char* mode = argv[2];
  int nogame = 0; std::vector<std::string> items;
  for (int i = 3; i < argc; i++) {
    std::string a = argv[i];
    if (a == "-rng" && i + 1 < argc) { std::string s = argv[++i]; size_t e = s.find('='); unsigned k = strtoul(s.substr(0, e).c_str(), 0, 0);
      std::string v = s.substr(e + 1); size_t p = 0; while (true) { rngForce[k].push_back(strtoul(v.c_str() + p, 0, 0)); p = v.find(',', p); if (p == std::string::npos) break; p++; } }
    else if (a == "-poke" && i + 1 < argc) { std::string s = argv[++i]; size_t e = s.find('='), c = s.find(':'); Poke p; p.a = strtoul(s.substr(0, e).c_str(), 0, 0);
      p.v = strtoul(s.substr(e + 1, c == std::string::npos ? std::string::npos : c - e - 1).c_str(), 0, 0); p.sz = c == std::string::npos ? 4 : atoi(s.substr(c + 1).c_str()); pokes.push_back(p); }
    else if (a == "-hold" && i + 1 < argc) holdSec = atof(argv[++i]);
    else if (a == "-nogame") nogame = 1;
    else items.push_back(a);
  }
  if (!strcmp(mode, "force")) for (auto& s : items) {
    Force f; size_t p = 0; f.id = (int)strtoul(s.c_str(), 0, 0);
    while ((p = s.find(':', p)) != std::string::npos) { p++; f.words.push_back(strtoul(s.c_str() + p, 0, 0)); }
    force.push_back(f);
  }
  PinmameConfig c = {PINMAME_AUDIO_FORMAT_INT16, 44100, "", OnState, OnDisplayAvailable, OnDisplayUpdated, NULL, NULL, NULL, NULL, OnSol, NULL, IsKeyPressed, OnLog, NULL};
  const char* nv = getenv("DEFF_TRACE_HOME");
  snprintf((char*)c.vpmPath, PINMAME_MAX_PATH, "%s/.pinmame/", nv ? nv : getenv("HOME"));
  PinmameSetConfig(&c); PinmameSetHandleKeyboard(1); PinmameSetHandleMechanics(0); PinmameSetDmdMode(PINMAME_DMD_MODE_RAW);
  PinmameSetArmHook(hook);
  if (PinmameRun("trn_174h") != PINMAME_STATUS_OK) { fprintf(stderr, "run fail\n"); return 1; }
  while (!PinmameIsRunning()) std::this_thread::sleep_for(std::chrono::milliseconds(10));
  std::this_thread::sleep_for(std::chrono::milliseconds(500)); waitemu(0.5);
  for (int s : {18, 19, 20, 21}) PinmameSetSwitch(s, 1);
  PinmameSetSwitch(41, 1); PinmameSetSwitch(53, 1); PinmameSetSwitch(54, 1);
  waitemu(8);
  fprintf(LOG, "%.4f READY\n", emu());
  if (!strcmp(mode, "play")) {
    // tracer.cpp play mode (trimmed): trough, shooter, scoop, random shots
    srand(atoi(items.size() > 0 ? items[0].c_str() : "1")); double dur = items.size() > 1 ? atof(items[1].c_str()) : 300;
    struct Shot { std::vector<int> sw; int w; };
    std::vector<Shot> shots = {{{35, 37}, 10}, {{38, 34}, 10}, {{43, 44, 44, 44}, 7}, {{46, 36, 36, 36}, 8}, {{39}, 6}, {{41}, 6},
      {{49}, 4}, {{50}, 4}, {{51}, 4}, {{1}, 3}, {{2}, 3}, {{3}, 3}, {{4}, 3}, {{7}, 2}, {{8}, 2}, {{13}, 2}, {{48}, 2},
      {{25}, 2}, {{28}, 2}, {{14}, 2}, {{12}, 3}, {{30}, 4}, {{31}, 4}, {{32}, 4}, {{26}, 4}, {{27}, 4}, {{11}, 5}, {{44}, 2}, {{36}, 2}};
    int tw = 0; for (auto& x : shots) tw += x.w;
    int trough = 4, inplay = 0, shooter = 0, scoop = 0, prevSol1 = 0, prevSol4 = 0, prevSol6 = 0, bankUp = 1, recogPos = 54;
    double shooterT = 0, nextShot = 0, gameIdle = emu(), recogT = 0;
    std::vector<double> drainAt;
    auto setTrough = [&]() { for (int i = 0; i < 4; i++) PinmameSetSwitch(21 - i, i < trough ? 1 : 0); };
    auto startGame = [&](double t) { int np = 1 + rand() % 2; fprintf(LOG, "%.4f PLAY start players=%d\n", t, np);
      for (int p = 0; p < np; p++) for (int k = 0; k < 4; k++) { waitemu(emu() + 0.3); keys[PINMAME_KEYCODE_NUMBER_5] = 1; waitemu(emu() + 0.3); keys[PINMAME_KEYCODE_NUMBER_5] = 0; }
      waitemu(emu() + 0.5); for (int p = 0; p < np; p++) { keys[PINMAME_KEYCODE_NUMBER_1] = 1; waitemu(emu() + 0.3); keys[PINMAME_KEYCODE_NUMBER_1] = 0; waitemu(emu() + 0.6); } gameIdle = emu(); };
    double t0 = emu(); startGame(t0);
    while (emu() < t0 + dur) {
      double t = emu();
      for (int q = 1; q <= 40; q++) sol[q] = PinmameGetSolenoid(q);
      int s1 = sol[1] > 0; if (s1 && !prevSol1 && trough > 0) { trough--; setTrough(); inplay++; shooter = 1; shooterT = t; PinmameSetSwitch(23, 1); drainAt.push_back(t + 20 + (rand() % 900) / 10.0); }
      prevSol1 = s1;
      if (shooter && t - shooterT > 1.2) { PinmameSetSwitch(23, 0); shooter = 0; }
      int s4 = sol[4] > 0; if (s4 && !prevSol4 && scoop) { PinmameSetSwitch(11, 0); scoop = 0; } prevSol4 = s4;
      int s6 = sol[6] > 0; if (s6 && !prevSol6) recogT = t; if (s6 && recogT > 0 && t - recogT > 0.6) { bankUp = !bankUp; PinmameSetSwitch(53, bankUp); PinmameSetSwitch(52, !bankUp); recogT = 0; } prevSol6 = s6;
      static double rt = 0; if (sol[23] > 0 && t - rt > 0.5) { PinmameSetSwitch(recogPos, 0); recogPos = recogPos == 56 ? 54 : recogPos + 1; PinmameSetSwitch(recogPos, 1); rt = t; }
      for (size_t i = 0; i < drainAt.size(); i++) if (t > drainAt[i] && !shooter && !scoop) { drainAt.erase(drainAt.begin() + i); inplay--; trough++; setTrough(); fprintf(LOG, "%.4f PLAY drain\n", emu()); break; }
      if (inplay > 0 && !shooter && !scoop && t > nextShot) {
        int rr = rand() % tw; size_t k = 0; for (; k < shots.size(); k++) { rr -= shots[k].w; if (rr < 0) break; }
        auto& sh = shots[k]; fprintf(LOG, "%.4f SWITCH %d\n", t, sh.sw[0]);
        for (int sw : sh.sw) { if (sw == 11) { PinmameSetSwitch(11, 1); scoop = 1; waitemu(emu() + 0.05); continue; }
          if (sw == 41) { PinmameSetSwitch(41, 0); waitemu(emu() + 0.03); PinmameSetSwitch(41, 1); waitemu(emu() + 0.05); continue; }
          PinmameSetSwitch(sw, 1); waitemu(emu() + 0.06); PinmameSetSwitch(sw, 0); waitemu(emu() + 0.15); }
        nextShot = emu() + 0.4 + (rand() % 150) / 100.0;
      }
      if (scoop && sol[4] == 0) { static double sc = 0; if (sc == 0) sc = t; if (t - sc > 15) { PinmameSetSwitch(11, 0); scoop = 0; sc = 0; } }
      if (inplay > 0) gameIdle = t;
      if (inplay == 0 && t - gameIdle > 25) startGame(t);
      std::this_thread::sleep_for(std::chrono::milliseconds(2));
      fflush(LOG);
    }
    PinmameStop(); fclose(LOG); return 0;
  }
  if (!nogame) {
    for (int k = 0; k < 4; k++) { waitemu(9 + k); keys[PINMAME_KEYCODE_NUMBER_5] = 1; waitemu(9.3 + k); keys[PINMAME_KEYCODE_NUMBER_5] = 0; }
    waitemu(13.5); keys[PINMAME_KEYCODE_NUMBER_1] = 1; waitemu(13.8); keys[PINMAME_KEYCODE_NUMBER_1] = 0;
    fprintf(LOG, "%.4f GAME_STARTED\n", emu());
  }
  nextForce = emu() + 5; forceArmed = 1;
  int ph = 0; double last = 0;
  while (true) {
    double t = emu();
    // simple ball sim: trough eject coil 1 -> ball to the shooter lane and stays there
    int s1 = PinmameGetSolenoid(1) > 0;
    if (s1 && ph == 0) { PinmameSetSwitch(18, 0); PinmameSetSwitch(23, 1); ph = 1; last = t; }
    if (ph == 1 && t - last > 0.5) { PinmameSetSwitch(18, 1); ph = 2; }
    if (forceArmed && forceIdx >= force.size() && curForce < 0 && t > nextForce) break;
    std::this_thread::sleep_for(std::chrono::milliseconds(5));
    fflush(LOG);
  }
  PinmameStop(); fclose(LOG); return 0;
}

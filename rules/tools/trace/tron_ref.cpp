// tron_ref: run the real Tron Legacy LE 1.74 ROM in libpinmame from a scenario script and
// write a reference trace (JSON lines) of everything the rules do: scores, display effects,
// sound calls, light effects, audits, game flags, lamps, coils and watched RAM variables.
//
// Build: needs libpinmame with tools/pinmame_arm_hook.patch applied (see README).
// Run:   PINMAME_NOJIT=1 ./tron_ref scenario.txt out.jsonl [watch.tsv]
#include <cstdio>
#include <cstdarg>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <string>
#include <vector>
#include <thread>
#include <chrono>
#include <mutex>
#include <atomic>
#include <condition_variable>
#include <sstream>
#include <unistd.h>
#include "libpinmame.h"
extern "C" {
void PinmameSetArmHook(void (*h)(unsigned int, unsigned int*));
unsigned int PinmameArmRead32(unsigned int a);
unsigned int PinmameArmRead8(unsigned int a);
void PinmameArmWrite32(unsigned int a, unsigned int d);
void PinmameArmWrite8(unsigned int a, unsigned int d);
double PinmameEmuTime();
}

static FILE* OUT;
static std::mutex mu;
static void emit(const char* fmt, ...) {
  va_list ap; va_start(ap, fmt);
  std::lock_guard<std::mutex> g(mu);
  fprintf(OUT, "{\"t\":%.4f,", PinmameEmuTime());
  vfprintf(OUT, fmt, ap);
  fprintf(OUT, "}\n");
  va_end(ap);
}
static unsigned r8(unsigned a){ return PinmameArmRead8(a); }
static unsigned r16(unsigned a){ return r8(a) | (r8(a+1)<<8); }
static unsigned r32(unsigned a){ return PinmameArmRead32(a); }

// ---- RAM locations (see tron/rules/developer_guide.md, "Reference trace")
static const unsigned RAM_CUR_PLAYER = 0x3817c;   // u8, 1-4
static const unsigned RAM_NUM_PLAYERS = 0x2110900; // u8
static const unsigned RAM_SCORES = 0x21109e4;     // u32[4]
static const unsigned RAM_TASK_CUR = 0x372c0;     // current task; deff id at +0x24

struct Watch { std::string name; unsigned addr; int size; long long last; };
static std::vector<Watch> watches;
static unsigned lastScore[4];
static int scoreInit = 0;

static void poll_ram() {
  for (int p = 0; p < 4; p++) {
    unsigned s = r32(RAM_SCORES + 4*p);
    if (!scoreInit) lastScore[p] = s;
    else if (s != lastScore[p]) {
      emit("\"ev\":\"score\",\"player\":%d,\"delta\":%lld,\"total\":%u", p+1, (long long)s - (long long)lastScore[p], s);
      lastScore[p] = s;
    }
  }
  scoreInit = 1;
  for (auto& w : watches) {
    long long v = w.size == 1 ? r8(w.addr) : w.size == 2 ? r16(w.addr) : r32(w.addr);
    if (w.size == 1 && v > 127 && w.name.find("signed") != std::string::npos) v -= 256;
    if (v != w.last) { emit("\"ev\":\"var\",\"name\":\"%s\",\"value\":%lld,\"old\":%lld", w.name.c_str(), v, w.last); w.last = v; }
  }
}

static std::mutex gmu; static std::condition_variable gcv;
static double target = 0; static bool parked = false; static bool gateOn = false;
static void gate() {
  if (!gateOn) return;
  double t = PinmameEmuTime();
  std::unique_lock<std::mutex> lk(gmu);
  if (t < target) return;
  parked = true; gcv.notify_all();
  gcv.wait(lk, [&]{ return PinmameEmuTime() < target || !gateOn; });
  parked = false;
}
static void hook(unsigned pc, unsigned* r) {
  switch (pc) {
  case 0x280b0: emit("\"ev\":\"deff_start\",\"id\":%u,\"caller\":\"0x%x\"", r[0] & 0xffff, r[14]); break;
  case 0x282e0: { static unsigned lastId = 0; static double lastT = -1; double t = PinmameEmuTime();
    if ((r[0] & 0xffff) != lastId || t - lastT > 1.0) emit("\"ev\":\"deff_stop\",\"id\":%u,\"caller\":\"0x%x\"", r[0] & 0xffff, r[14]);
    lastId = r[0] & 0xffff; lastT = t; break; }
  case 0x2c744: { unsigned tk = r32(RAM_TASK_CUR); unsigned d = tk ? r16(tk+0x24) : 0;
    emit("\"ev\":\"sound\",\"call\":\"0x%03x\",\"in_deff\":%u,\"caller\":\"0x%x\"", r[0] & 0xffff, d, r[14]); break; }
  case 0x87ac: emit("\"ev\":\"leff_start\",\"id\":%u,\"caller\":\"0x%x\"", r[0] & 0xffff, r[14]); break;
  case 0xc404: emit("\"ev\":\"leff_stop\",\"id\":%u,\"caller\":\"0x%x\"", r[0] & 0xffff, r[14]); break;
  case 0xb624: case 0xb718: case 0xb76c: emit("\"ev\":\"task_start\",\"task\":\"0x%x\",\"fn\":\"0x%x\",\"caller\":\"0x%x\"", r[0] & 0xffff, r[1], r[14]); break;
  case 0x101b824: emit("\"ev\":\"tube_show_start\",\"id\":%u,\"caller\":\"0x%x\"", r[0] & 0xffff, r[14]); break;
  case 0x101baac: emit("\"ev\":\"tube_show_stop\",\"id\":%u,\"caller\":\"0x%x\"", r[0] & 0xffff, r[14]); break;
  case 0x178c: emit("\"ev\":\"audit\",\"id\":%u,\"n\":%d,\"caller\":\"0x%x\"", r[0] & 0xffff, (int)r[1], r[14]); break;
  case 0x65d8: emit("\"ev\":\"flag_set\",\"flag\":%u,\"caller\":\"0x%x\"", r[0] & 0xffff, r[14]); break;
  case 0x6588: emit("\"ev\":\"flag_clear\",\"flag\":%u,\"caller\":\"0x%x\"", r[0] & 0xffff, r[14]); break;
  case 0x2340c: emit("\"ev\":\"score_add\",\"points\":%d,\"multiplier\":%u,\"player\":%u,\"caller\":\"0x%x\"", (int)r[0], r8(0x38180), r8(RAM_CUR_PLAYER), r[14]); break;
  case 0x1ed7c: emit("\"ev\":\"multiball_start\",\"balls\":%u,\"save_ticks\":%u,\"grace_ticks\":%u,\"caller\":\"0x%x\"", r[0] & 0xff, r[2], r[3], r[14]); break;
  case 0xb91c: poll_ram(); gate(); break;
  }
}

static std::atomic<int> keys[256];
int PINMAMECALLBACK IsKeyPressed(PINMAME_KEYCODE k, void*) { return (int)k < 256 ? keys[(int)k].load() : 0; }
void PINMAMECALLBACK OnDisplayAvailable(int, int, PinmameDisplayLayout*, void*) {}
void PINMAMECALLBACK OnDisplayUpdated(int, void*, PinmameDisplayLayout*, void*) {}
void PINMAMECALLBACK OnState(int, void*) {}
void PINMAMECALLBACK OnLog(PINMAME_LOG_LEVEL l, const char* f, va_list a, void*) { if (l == PINMAME_LOG_LEVEL_ERROR) { vfprintf(stderr, f, a); fprintf(stderr, "\n"); } }
static int sol[64];
void PINMAMECALLBACK OnSol(PinmameSolenoidState* s, void*) {
  if (s->solNo < 64) { int on = s->state > 0; if (on != (sol[s->solNo] > 0)) emit("\"ev\":\"coil\",\"coil\":%d,\"on\":%d", s->solNo, on); sol[s->solNo] = s->state; }
}

// ---- ball / mech simulation
static int trough = 4, shooter = 0, inplay = 0, scoop = 0, bankUp = 1, recogPos = 54;
static double shooterAt = 0, autoPlunge = 1.0, recogMoveT = 0, bankT = 0;
static int prev[64];
static void setTrough() { for (int i = 0; i < 4; i++) PinmameSetSwitch(21 - i, i < trough ? 1 : 0); }
static double emu() { return PinmameEmuTime(); }
static void step_to(double t);
static void sim_step() {
  double t = emu();
  // poll every coil: libpinmame does not report all of them through the callback
  for (int i = 1; i < 40; i++) { int v = PinmameGetSolenoid(i); int on = v > 0; if (on != (sol[i] > 0)) emit("\"ev\":\"coil\",\"coil\":%d,\"on\":%d", i, on); sol[i] = v; }
  // coil 1: trough eject -> ball to shooter lane
  if (sol[1] > 0 && prev[1] == 0 && trough > 0 && !shooter) { trough--; setTrough(); shooter = 1; shooterAt = t; PinmameSetSwitch(23, 1); emit("\"ev\":\"sim\",\"what\":\"trough_eject\",\"trough\":%d", trough); }
  // coil 2: auto launch
  if (sol[2] > 0 && prev[2] == 0 && shooter) { shooter = 0; inplay++; PinmameSetSwitch(23, 0); emit("\"ev\":\"sim\",\"what\":\"launched\",\"in_play\":%d", inplay); }
  if (shooter && autoPlunge > 0 && t - shooterAt > autoPlunge) { shooter = 0; inplay++; PinmameSetSwitch(23, 0); emit("\"ev\":\"sim\",\"what\":\"plunged\",\"in_play\":%d", inplay); }
  // coil 4: video game (Flynn's Arcade) scoop eject
  if (sol[4] > 0 && prev[4] == 0 && scoop) { scoop = 0; PinmameSetSwitch(11, 0); emit("\"ev\":\"sim\",\"what\":\"scoop_eject\""); }
  // coil 6: recognizer 3-bank motor toggles up/down
  if (sol[6] > 0 && prev[6] == 0) bankT = t;
  if (sol[6] > 0 && bankT > 0 && t - bankT > 0.6) { bankUp = !bankUp; PinmameSetSwitch(53, bankUp); PinmameSetSwitch(52, !bankUp); bankT = 0; emit("\"ev\":\"sim\",\"what\":\"bank_%s\"", bankUp ? "up" : "down"); }
  // coil 23: recognizer motor walks positions 54-56
  if (sol[23] > 0 && t - recogMoveT > 0.5) { PinmameSetSwitch(recogPos, 0); recogPos = recogPos == 56 ? 54 : recogPos + 1; PinmameSetSwitch(recogPos, 1); recogMoveT = t; }
  for (int i = 0; i < 64; i++) prev[i] = sol[i] > 0;
  // lamps
  static PinmameLampState ls[512];
  int n = PinmameGetChangedLamps(ls);
  for (int i = 0; i < n; i++) emit("\"ev\":\"lamp\",\"lamp\":%d,\"state\":%d", ls[i].lampNo, ls[i].state);
}
static void step_to(double t) {
  while (true) {
    double cur = emu();
    if (cur >= t) break;
    double nt = cur + 0.005; if (nt > t) nt = t;
    { std::unique_lock<std::mutex> lk(gmu); target = nt; parked = false; gcv.notify_all();
      gcv.wait(lk, [&]{ return parked; }); }
    sim_step();
  }
}
static void pulse(int sw, double ms) {
  int nc = (sw == 41);   // disc opto reads closed when nothing is there
  PinmameSetSwitch(sw, nc ? 0 : 1); step_to(emu() + ms / 1000.0); PinmameSetSwitch(sw, nc ? 1 : 0);
}
static void set_adj(int id, unsigned v) {
  unsigned rec = 0x040de218 + id * 32; unsigned ptr = r32(rec);
  PinmameArmWrite32(ptr, v);
  unsigned char s = 0; for (int i = 0; i < 4; i++) s += (v >> (8*i)) & 0xff;
  PinmameArmWrite8(ptr + 4, (unsigned char)~s);
}

int main(int argc, char** argv) {
  if (argc < 3) { fprintf(stderr, "usage: tron_ref scenario.txt out.jsonl [watch.tsv]\n"); return 2; }
  FILE* sc = fopen(argv[1], "r"); if (!sc) { perror(argv[1]); return 1; }
  OUT = fopen(argv[2], "w");
  if (argc > 3) { FILE* w = fopen(argv[3], "r"); char line[256];
    while (w && fgets(line, sizeof line, w)) { if (line[0] == '#' || line[0] == '\n') continue;
      char nm[128]; unsigned a; int sz; if (sscanf(line, "%127s %x %d", nm, &a, &sz) == 3) watches.push_back({nm, a, sz, -1}); }
    if (w) fclose(w); }
  PinmameConfig c = { PINMAME_AUDIO_FORMAT_INT16, 44100, "", OnState, OnDisplayAvailable, OnDisplayUpdated, NULL, NULL, NULL, NULL, OnSol, NULL, IsKeyPressed, OnLog, NULL };
  // fresh NVRAM per run (factory settings), ROM zip from $TRON_ROMS or ~/.pinmame/roms
  char tmpl[] = "/tmp/tron_ref_XXXXXX"; char* dir = mkdtemp(tmpl);
  std::string roms = getenv("TRON_ROMS") ? getenv("TRON_ROMS") : std::string(getenv("HOME")) + "/.pinmame/roms";
  std::string cmd = std::string("mkdir -p ") + dir + "/nvram && ln -s " + roms + " " + dir + "/roms";
  if (system(cmd.c_str()) != 0) { fprintf(stderr, "setup failed\n"); return 1; }
  snprintf((char*)c.vpmPath, PINMAME_MAX_PATH, "%s/", dir);
  PinmameSetConfig(&c); PinmameSetHandleKeyboard(1); PinmameSetHandleMechanics(0); PinmameSetDmdMode(PINMAME_DMD_MODE_RAW);
  PinmameSetArmHook(hook);
  if (PinmameRun("trn_174h") != PINMAME_STATUS_OK) { fprintf(stderr, "run fail\n"); return 1; }
  while (!PinmameIsRunning()) std::this_thread::sleep_for(std::chrono::milliseconds(10));
  std::this_thread::sleep_for(std::chrono::milliseconds(500));
  while (emu() < 0.5) std::this_thread::sleep_for(std::chrono::milliseconds(2));
  { std::unique_lock<std::mutex> lk(gmu); target = emu() + 0.01; gateOn = true; }
  PinmameSetSwitch(41, 1); PinmameSetSwitch(53, 1); PinmameSetSwitch(54, 1);
  setTrough();
  step_to(8.0);   // boot
  emit("\"ev\":\"ready\"");
  char line[512];
  while (fgets(line, sizeof line, sc)) {
    char* h = strchr(line, '#'); if (h) *h = 0;
    std::istringstream is(line); std::string cmd; if (!(is >> cmd)) continue;
    if (cmd == "wait") { double s; is >> s; step_to(emu() + s); }
    else if (cmd == "hit") { int sw; double ms = 60; is >> sw; is >> ms; emit("\"ev\":\"switch\",\"sw\":%d", sw);
      if (sw == 11) { scoop = 1; PinmameSetSwitch(11, 1); step_to(emu() + 0.05); } else pulse(sw, ms);
      step_to(emu() + 0.1); }
    else if (cmd == "hold") { int sw; is >> sw; emit("\"ev\":\"switch_hold\",\"sw\":%d", sw); PinmameSetSwitch(sw, 1); }
    else if (cmd == "release") { int sw; is >> sw; emit("\"ev\":\"switch_release\",\"sw\":%d", sw); PinmameSetSwitch(sw, 0); }
    else if (cmd == "start") { int players = 1; is >> players;
      for (int p = 0; p < players; p++) for (int k = 0; k < 3; k++) { keys[PINMAME_KEYCODE_NUMBER_5] = 1; step_to(emu() + 0.3); keys[PINMAME_KEYCODE_NUMBER_5] = 0; step_to(emu() + 0.3); }
      for (int p = 0; p < players; p++) { keys[PINMAME_KEYCODE_NUMBER_1] = 1; step_to(emu() + 0.3); keys[PINMAME_KEYCODE_NUMBER_1] = 0; step_to(emu() + 0.6); }
      emit("\"ev\":\"script\",\"what\":\"start\",\"players\":%d", players); }
    else if (cmd == "drain") { std::string via; is >> via;
      if (inplay <= 0) { emit("\"ev\":\"sim\",\"what\":\"drain_ignored_no_ball\""); continue; }
      if (via == "left") pulse(24, 60); else if (via == "right") pulse(29, 60);
      inplay--; trough++; setTrough(); emit("\"ev\":\"sim\",\"what\":\"drain\",\"in_play\":%d,\"trough\":%d", inplay, trough); step_to(emu() + 0.1); }
    else if (cmd == "plunge") { if (shooter) { shooter = 0; inplay++; PinmameSetSwitch(23, 0); emit("\"ev\":\"sim\",\"what\":\"plunged\",\"in_play\":%d", inplay); } }
    else if (cmd == "autoplunge") { is >> autoPlunge; }
    else if (cmd == "adj") { int id; unsigned v; is >> id >> v; set_adj(id, v); emit("\"ev\":\"script\",\"what\":\"adj\",\"id\":%d,\"value\":%u", id, v); }
    else if (cmd == "poke") { unsigned a, v, sz = 1; is >> std::hex >> a >> std::dec >> v >> sz; if (sz == 4) PinmameArmWrite32(a, v); else PinmameArmWrite8(a, v); emit("\"ev\":\"script\",\"what\":\"poke\",\"addr\":\"0x%x\",\"value\":%u", a, v); }
    else if (cmd == "button") {   // button left|right|tilt|tournament|start [ms]  (pulse; ms=-1 holds, 0 releases)
      std::string b; double ms = 100; is >> b >> ms;
      int k = b == "left" ? PINMAME_KEYCODE_LEFT_SHIFT : b == "right" ? PINMAME_KEYCODE_RIGHT_SHIFT : b == "tilt" ? PINMAME_KEYCODE_INSERT
            : b == "tournament" ? PINMAME_KEYCODE_NUMBER_2 : b == "start" ? PINMAME_KEYCODE_NUMBER_1 : -1;
      if (k < 0) { fprintf(stderr, "unknown button %s\n", b.c_str()); continue; }
      emit("\"ev\":\"button\",\"button\":\"%s\",\"ms\":%g", b.c_str(), ms);
      if (ms < 0) keys[k] = 1; else if (ms == 0) keys[k] = 0; else { keys[k] = 1; step_to(emu() + ms / 1000.0); keys[k] = 0; step_to(emu() + 0.05); } }
    else if (cmd == "mark") { std::string rest; std::getline(is, rest); emit("\"ev\":\"mark\",\"text\":\"%s\"", rest.c_str() + (rest.size() && rest[0] == ' ')); }
    else fprintf(stderr, "unknown command: %s\n", cmd.c_str());
  }
  step_to(emu() + 0.5);
  emit("\"ev\":\"end\"");
  { std::unique_lock<std::mutex> lk(gmu); gateOn = false; gcv.notify_all(); }
  PinmameStop(); fclose(OUT); return 0;
}

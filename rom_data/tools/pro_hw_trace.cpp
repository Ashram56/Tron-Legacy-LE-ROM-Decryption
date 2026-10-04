// pro_hw_trace: hw_trace.cpp ported to Tron PRO 1.74 (PinMAME set trn_17402 = TRN174VP.BIN). Generated from hw_trace.cpp by
// replacing every LE address with its Pro counterpart (rom_data/pro/le_to_pro_functions.csv for functions, the literal-pool
// RAM map for RAM): coil IRQ 0x11628, coil shadow 0x34064, power mask 0x3406c, task_sleep 0xae74, deff_start 0x21bcc,
// leff_start 0x7d88, shaker_run 0x010203ac. The Recognizer motor sim is dropped (coil 23 is a flasher on the Pro).
// ROM zip: $TRON_ROMS/trn_17402.zip holding trn_17402.bin. Build and run as hw_trace.cpp.
// hw_trace: tron_ref (rules/tools/trace/tron_ref.cpp) extended for the coil/lamp hardware study
// (rom_data/io/). Same scenario language, plus:
//   * drv events: coil driver outputs sampled at the entry of the 250 us IO interrupt service
//     FUN_00012070 (shadow 0x34064[0..4], masked by 0x3406c unless (0x30070 & 3) == 3), so
//     on-times are measured to one IRQ period instead of the 5 ms polling of tron_ref.
//   * call events for every coil API entry (coil, time, pattern, stack args, caller lr).
//   * tread events: the first time each (pc, address) reads one of the hardware tables
//     (coil descriptors, bumper/sling rules, devices, coil groups, lamp groups, leff table).
//   * dump events at the end: the runtime hardware-rule objects (0x30058/0x30040/0x30044).
//   * scenario commands: `key 7|8|9|0|end MS` (coin door Back/Minus/Plus/Select/door toggle),
//     `inject ADDR r0 r1 r2 r3 [s0 s1 ...]` (call ROM function ADDR from the next task_sleep,
//     stack args s0.. pushed for the callee), `irqcount` marker.
// Build: g++ -O2 -std=c++17 -I/home/claude/pinmame/src/libpinmame hw_trace.cpp \
//   -L/home/claude/pinmame/build -lpinmame -lpthread -Wl,-rpath,/home/claude/pinmame/build -o hw_trace
// Run:   PINMAME_NOJIT=1 ./hw_trace scenario.txt out.jsonl
#include <cstdio>
#include <cstdarg>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <string>
#include <vector>
#include <set>
#include <map>
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
static std::recursive_mutex mu;
static void emit(const char* fmt, ...) {
  va_list ap; va_start(ap, fmt);
  std::lock_guard<std::recursive_mutex> g(mu);
  fprintf(OUT, "{\"t\":%.6f,", PinmameEmuTime());
  vfprintf(OUT, fmt, ap);
  fprintf(OUT, "}\n");
  va_end(ap);
}
static unsigned r8(unsigned a){ return PinmameArmRead8(a); }
static unsigned r16(unsigned a){ return r8(a) | (r8(a+1)<<8); }
static unsigned r32(unsigned a){ return PinmameArmRead32(a); }

// ---- ROM image for decoding load instructions
static std::vector<unsigned char> ROMIMG;
static inline bool code_word(unsigned pc, unsigned& w) {
  size_t o;
  if (pc < 0x2fa00) o = pc; else if (pc >= 0x01000000 && pc < 0x01100000) o = pc - 0x01000000 + 0x40000; else return false;
  if (o + 4 > ROMIMG.size()) return false;
  w = ROMIMG[o] | (ROMIMG[o+1]<<8) | (ROMIMG[o+2]<<16) | ((unsigned)ROMIMG[o+3]<<24); return true;
}
static bool cond_ok(unsigned w, unsigned cpsr) {
  unsigned c = w >> 28; bool N = cpsr>>31&1, Z = cpsr>>30&1, C = cpsr>>29&1, V = cpsr>>28&1;
  switch (c) { case 0: return Z; case 1: return !Z; case 2: return C; case 3: return !C; case 4: return N; case 5: return !N;
    case 6: return V; case 7: return !V; case 8: return C && !Z; case 9: return !C || Z; case 10: return N == V; case 11: return N != V;
    case 12: return !Z && N == V; case 13: return Z || N != V; case 14: return true; default: return false; }
}
// effective address of a load at pc, or 0
static unsigned load_ea(unsigned pc, unsigned* r, int& size) {
  unsigned w; if (!code_word(pc, w)) return 0;
  if (!cond_ok(w, r[16])) return 0;
  auto reg = [&](unsigned n) { return n == 15 ? pc + 8 : r[n]; };
  if ((w & 0x0c100000) == 0x04100000) {            // LDR/LDRB
    unsigned rn = (w >> 16) & 15, off;
    if (w & (1u<<25)) { unsigned rm = w & 15, sh = (w >> 7) & 31, ty = (w >> 5) & 3; if (w & 0x10) return 0;
      off = reg(rm); if (ty == 0) off <<= sh; else if (ty == 1) off = sh ? off >> sh : 0; else if (ty == 2) off = sh ? (unsigned)((int)off >> sh) : 0; }
    else off = w & 0xfff;
    unsigned base = reg(rn); unsigned ea = (w & (1u<<24)) ? ((w & (1u<<23)) ? base + off : base - off) : base;
    size = (w & (1u<<22)) ? 1 : 4; return ea;
  }
  if ((w & 0x0e100090) == 0x00100090 && (w & 0x60)) {  // LDRH/LDRSB/LDRSH
    unsigned rn = (w >> 16) & 15, off = (w & (1u<<22)) ? (((w >> 4) & 0xf0) | (w & 15)) : reg(w & 15);
    unsigned base = reg(rn); unsigned ea = (w & (1u<<24)) ? ((w & (1u<<23)) ? base + off : base - off) : base;
    size = ((w >> 5) & 3) == 2 ? 1 : 2; return ea;
  }
  if ((w & 0x0e100000) == 0x08100000) { size = 4 * __builtin_popcount(w & 0xffff); return reg((w >> 16) & 15); }  // LDM (start)
  return 0;
}
struct Range { unsigned lo, hi; const char* name; };
static const Range RANGES[] = {
  {0x040c6254, 0x040c6644, "coil_desc"},      // Pro: 36 x 28
  {0x040c7398, 0x040c73fc, "coil_groups"},
  {0x040c76b0, 0x040c7e30, "leff_table"},
};
static std::set<std::pair<unsigned,unsigned>> seenRead;
static void check_read(unsigned pc, unsigned* r) {
  int size = 0; unsigned ea = load_ea(pc, r, size); if (!ea) return;
  for (auto& g : RANGES) if (ea >= g.lo && ea < g.hi) {
    if (seenRead.insert({pc, ea}).second) emit("\"ev\":\"tread\",\"tab\":\"%s\",\"pc\":\"0x%x\",\"ea\":\"0x%x\",\"size\":%d,\"lr\":\"0x%x\"", g.name, pc, ea, size, r[14]);
    return;
  }
}

// ---- coil driver outputs at IRQ granularity
static unsigned char lastOut[5]; static int outInit = 0; static unsigned long long irqN = 0;
static double drvOnAt[48];
static void sample_drivers() {
  irqN++;
  unsigned pw = r32(0x30070) & 3;
  unsigned char cur[5];
  for (int i = 0; i < 5; i++) { unsigned char s = r8(0x34064 + i); if (i < 4 && pw != 3) s &= r8(0x3406c + i); cur[i] = s; }
  if (!outInit) { memcpy(lastOut, cur, 5); outInit = 1; return; }
  double t = PinmameEmuTime();
  for (int i = 0; i < 5; i++) if (cur[i] != lastOut[i]) for (int b = 0; b < 8; b++) {
    int was = lastOut[i] >> b & 1, now = cur[i] >> b & 1; if (was == now) continue;
    int coil = i * 8 + b + 1;
    if (now) { drvOnAt[coil] = t; emit("\"ev\":\"drv\",\"coil\":%d,\"on\":1,\"irq\":%llu", coil, irqN); }
    else emit("\"ev\":\"drv\",\"coil\":%d,\"on\":0,\"irq\":%llu,\"on_ms\":%.3f", coil, irqN, (t - drvOnAt[coil]) * 1000.0);
  }
  memcpy(lastOut, cur, 5);
}

// ---- call injection through task_sleep
struct Inject { unsigned addr; unsigned a[4]; std::vector<unsigned> stk; };
static std::vector<Inject> injq; static std::mutex injmu;
static int injecting = 0; static unsigned sv[17]; static unsigned svsp = 0;

static void poll_ram();
static void gate();
static void hook(unsigned pc, unsigned* r) {
  check_read(pc, r);
  switch (pc) {
  case 0x11628: sample_drivers(); break;
  // coil API (os_api.json names; raw FUN_ names for the rest)
  case 0x5f98: emit("\"ev\":\"call\",\"fn\":\"coil_pulse\",\"coil\":%u,\"ms\":%u,\"lr\":\"0x%x\"", r[0]&0xff, r[1]&0xffff, r[14]); break;
  case 0x5fe8: emit("\"ev\":\"call\",\"fn\":\"coil_pulse_fn\",\"coil\":%u,\"ms\":%u,\"pattern\":\"0x%08x\",\"lr\":\"0x%x\"", r[0]&0xff, r[1]&0xffff, r[2], r[14]); break;
  case 0x21f0: case 0x22d8: case 0x20e8: case 0x2188:
    emit("\"ev\":\"call\",\"fn\":\"0x%x\",\"coil\":%u,\"ms\":%u,\"cb\":\"0x%x\",\"a3\":\"0x%x\",\"s0\":\"0x%x\",\"sync\":%u,\"lr\":\"0x%x\"", pc, r[0]&0xff, r[1]&0xffff, r[2], r[3], r32(r[13]), r32(r[13]+4)&0xff, r[14]); break;
  case 0x2340: case 0x2408:
    emit("\"ev\":\"call\",\"fn\":\"0x%x\",\"coil\":%u,\"ms\":%u,\"pattern\":\"0x%08x\",\"bits\":%u,\"cb\":\"0x%x\",\"s1\":\"0x%x\",\"s2\":\"0x%x\",\"sync\":%u,\"lr\":\"0x%x\"", pc, r[0]&0xff, r[1]&0xffff, r[2], r[3]&0xff, r32(r[13]), r32(r[13]+4), r32(r[13]+8), r32(r[13]+12)&0xff, r[14]); break;
  case 0x2484: case 0x255c:
    emit("\"ev\":\"call\",\"fn\":\"0x%x\",\"coil\":%u,\"ms\":%u,\"on\":%u,\"off\":%u,\"cb\":\"0x%x\",\"s1\":\"0x%x\",\"s2\":\"0x%x\",\"sync\":%u,\"lr\":\"0x%x\"", pc, r[0]&0xff, r[1]&0xffff, r[2]&0xffff, r[3]&0xffff, r32(r[13]), r32(r[13]+4), r32(r[13]+8), r32(r[13]+12)&0xff, r[14]); break;
  case 0x25e4: emit("\"ev\":\"call\",\"fn\":\"coil_off\",\"coil\":%u,\"lr\":\"0x%x\"", r[0]&0xff, r[14]); break;
  case 0x265c: emit("\"ev\":\"call\",\"fn\":\"coil_on\",\"coil\":%u,\"lr\":\"0x%x\"", r[0]&0xff, r[14]); break;
  case 0x6048: emit("\"ev\":\"call\",\"fn\":\"coil_pulse_stop\",\"coil\":%u,\"lr\":\"0x%x\"", r[0]&0xff, r[14]); break;
  case 0x614c: emit("\"ev\":\"call\",\"fn\":\"coilgroup_pulse\",\"group\":%u,\"ms\":%u,\"lr\":\"0x%x\"", r[0]&0xffff, r[1]&0xffff, r[14]); break;
  case 0x61bc: emit("\"ev\":\"call\",\"fn\":\"coilgroup_pulse_fn\",\"group\":%u,\"ms\":%u,\"pattern\":\"0x%08x\",\"lr\":\"0x%x\"", r[0]&0xffff, r[1]&0xffff, r[2], r[14]); break;
  case 0x630c: { unsigned d = r[0]; unsigned p = r32(d), n = r32(d+4), sz = r32(d+8);
    emit("\"ev\":\"call\",\"fn\":\"hwrule_init\",\"desc\":\"0x%x\",\"ptr\":\"0x%x\",\"count\":%u,\"size\":%u,\"lr\":\"0x%x\"", d, p, n, sz, r[14]);
    for (unsigned i = 0; i < n && i < 32; i++) { char hex[200] = {0}; for (unsigned k = 0; k < sz && k < 64; k++) sprintf(hex + 2*k, "%02x", r8(p + i*sz + k));
      emit("\"ev\":\"hwrule_src\",\"i\":%u,\"addr\":\"0x%x\",\"hex\":\"%s\"", i, p + i*sz, hex); }
    break; }
  case 0x673c: emit("\"ev\":\"call\",\"fn\":\"hwrule_reenable\",\"i\":%u,\"lr\":\"0x%x\"", r[0], r[14]); break;
  case 0x6624: emit("\"ev\":\"call\",\"fn\":\"hwrule_disable\",\"i\":%u,\"lr\":\"0x%x\"", r[0], r[14]); break;
  case 0x66b8: emit("\"ev\":\"call\",\"fn\":\"hwrule_enable\",\"i\":%u,\"lr\":\"0x%x\"", r[0], r[14]); break;
  case 0x2fac: emit("\"ev\":\"call\",\"fn\":\"bumper_enable\",\"i\":%u,\"on\":%u,\"lr\":\"0x%x\"", r[0]&0xff, r[1]&0xff, r[14]); break;
  case 0x34a8: emit("\"ev\":\"call\",\"fn\":\"sling_enable\",\"i\":%u,\"on\":%u,\"lr\":\"0x%x\"", r[0]&0xff, r[1]&0xff, r[14]); break;
  case 0x10203ac: emit("\"ev\":\"call\",\"fn\":\"shaker_run\",\"strength\":%u,\"min\":%u,\"lr\":\"0x%x\"", r[0], r[1], r[14]); break;
  // rules-level events (as tron_ref)
  case 0x21bcc: emit("\"ev\":\"deff_start\",\"id\":%u,\"caller\":\"0x%x\"", r[0] & 0xffff, r[14]); break;
  case 0x7d88: emit("\"ev\":\"leff_start\",\"id\":%u,\"caller\":\"0x%x\"", r[0] & 0xffff, r[14]); break;
  case 0xae74: {
    if (injecting) {
      if (r[13] == svsp) { for (int i = 0; i < 4; i++) r[i] = sv[i]; r[13] = sv[13]; r[14] = sv[14]; injecting = 0; emit("\"ev\":\"inject_done\""); }
      break;
    }
    { std::lock_guard<std::mutex> g(injmu);
      if (!injq.empty()) { Inject j = injq.front(); injq.erase(injq.begin());
        for (int i = 0; i < 16; i++) sv[i] = r[i];
        unsigned sp = r[13] - 4 * (unsigned)j.stk.size() - 16;   // keep 16 bytes of slack, args at sp
        for (size_t k = 0; k < j.stk.size(); k++) PinmameArmWrite32(sp + 4*k, j.stk[k]);
        for (int i = 0; i < 4; i++) r[i] = j.a[i];
        r[13] = sp; svsp = sp; r[14] = 0xae74; r[15] = j.addr; injecting = 1;
        emit("\"ev\":\"inject\",\"addr\":\"0x%x\",\"r0\":%u,\"r1\":%u,\"r2\":%u,\"r3\":%u,\"nstk\":%zu", j.addr, j.a[0], j.a[1], j.a[2], j.a[3], j.stk.size());
        break; } }
    poll_ram(); gate(); break; }
  }
}

static unsigned lastScore[4]; static int scoreInit = 0;
static void poll_ram() {
  for (int p = 0; p < 4; p++) { unsigned s = r32(0x21109e4 + 4*p); if (scoreInit && s != lastScore[p]) emit("\"ev\":\"score\",\"player\":%d,\"total\":%u", p+1, s); lastScore[p] = s; }
  scoreInit = 1;
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

static std::atomic<int> keys[256];
int PINMAMECALLBACK IsKeyPressed(PINMAME_KEYCODE k, void*) { return (int)k < 256 ? keys[(int)k].load() : 0; }
void PINMAMECALLBACK OnDisplayAvailable(int, int, PinmameDisplayLayout*, void*) {}
void PINMAMECALLBACK OnDisplayUpdated(int, void*, PinmameDisplayLayout*, void*) {}
void PINMAMECALLBACK OnState(int, void*) {}
void PINMAMECALLBACK OnLog(PINMAME_LOG_LEVEL l, const char* f, va_list a, void*) { if (l == PINMAME_LOG_LEVEL_ERROR) { vfprintf(stderr, f, a); fprintf(stderr, "\n"); } }
static int sol[64];
void PINMAMECALLBACK OnSol(PinmameSolenoidState* s, void*) {}

// ---- ball / mech simulation (as tron_ref)
static int trough = 4, shooter = 0, inplay = 0, scoop = 0, bankUp = 1, recogPos = 54;
static double shooterAt = 0, autoPlunge = 1.0, recogMoveT = 0, bankT = 0;
static int prev[64];
static void setTrough() { for (int i = 0; i < 4; i++) PinmameSetSwitch(21 - i, i < trough ? 1 : 0); }
static double emu() { return PinmameEmuTime(); }
static void sim_step() {
  double t = emu();
  for (int i = 1; i < 40; i++) { int v = PinmameGetSolenoid(i); int on = v > 0; if (on != (sol[i] > 0)) emit("\"ev\":\"coil\",\"coil\":%d,\"on\":%d", i, on); sol[i] = v; }
  if (sol[1] > 0 && prev[1] == 0 && trough > 0 && !shooter) { trough--; setTrough(); shooter = 1; shooterAt = t; PinmameSetSwitch(23, 1); emit("\"ev\":\"sim\",\"what\":\"trough_eject\",\"trough\":%d", trough); }
  if (sol[2] > 0 && prev[2] == 0 && shooter) { shooter = 0; inplay++; PinmameSetSwitch(23, 0); emit("\"ev\":\"sim\",\"what\":\"launched\",\"in_play\":%d", inplay); }
  if (shooter && autoPlunge > 0 && t - shooterAt > autoPlunge) { shooter = 0; inplay++; PinmameSetSwitch(23, 0); emit("\"ev\":\"sim\",\"what\":\"plunged\",\"in_play\":%d", inplay); }
  if (sol[4] > 0 && prev[4] == 0 && scoop) { scoop = 0; PinmameSetSwitch(11, 0); emit("\"ev\":\"sim\",\"what\":\"scoop_eject\""); }
  if (sol[6] > 0 && prev[6] == 0) bankT = t;
  if (sol[6] > 0 && bankT > 0 && t - bankT > 0.6) { bankUp = !bankUp; PinmameSetSwitch(53, bankUp); PinmameSetSwitch(52, !bankUp); bankT = 0; emit("\"ev\":\"sim\",\"what\":\"bank_%s\"", bankUp ? "up" : "down"); }
    for (int i = 0; i < 64; i++) prev[i] = sol[i] > 0;
}
static void step_to(double t) {
  while (true) {
    double cur = emu(); if (cur >= t) break;
    double nt = cur + 0.005; if (nt > t) nt = t;
    { std::unique_lock<std::mutex> lk(gmu); target = nt; parked = false; gcv.notify_all(); gcv.wait(lk, [&]{ return parked; }); }
    sim_step();
  }
}
static void pulse(int sw, double ms) {
  int nc = (sw == 41);
  PinmameSetSwitch(sw, nc ? 0 : 1); step_to(emu() + ms / 1000.0); PinmameSetSwitch(sw, nc ? 1 : 0);
}
static void dump_rules() {
  unsigned base = r32(0x30058), n = r32(0x3005c);
  for (unsigned i = 0; i < n && base; i++) { char hex[200] = {0}; for (int k = 0; k < 0x40; k++) sprintf(hex + 2*k, "%02x", r8(base + i*0x40 + k));
    emit("\"ev\":\"dump\",\"what\":\"hwrule\",\"i\":%u,\"hex\":\"%s\"", i, hex); }
  unsigned b2 = r32(0x30040); for (unsigned i = 1; i < 4 && b2; i++) { char hex[80] = {0}; for (int k = 0; k < 0x20; k++) sprintf(hex + 2*k, "%02x", r8(b2 + i*0x20 + k)); emit("\"ev\":\"dump\",\"what\":\"bumper\",\"i\":%u,\"hex\":\"%s\"", i, hex); }
  unsigned b3 = r32(0x30044); for (unsigned i = 1; i < 3 && b3; i++) { char hex[80] = {0}; for (int k = 0; k < 0x1c; k++) sprintf(hex + 2*k, "%02x", r8(b3 + i*0x1c + k)); emit("\"ev\":\"dump\",\"what\":\"sling\",\"i\":%u,\"hex\":\"%s\"", i, hex); }
  emit("\"ev\":\"dump\",\"what\":\"power\",\"v3727c\":\"0x%x\",\"mask\":\"%02x%02x%02x%02x\",\"zc_ok\":%u,\"zc_per_s\":%u", r32(0x30070), r8(0x3406c), r8(0x3406d), r8(0x3406e), r8(0x3406f), r8(0x30100), r32(0x3010c));
}

int main(int argc, char** argv) {
  if (argc < 3) { fprintf(stderr, "usage: hw_trace scenario.txt out.jsonl\n"); return 2; }
  { const char* rp = getenv("TRON_ROM") ? getenv("TRON_ROM") : "/mnt/project-files/tron/pro/TRN174VP.BIN"; FILE* f = fopen(rp, "rb"); if (!f) { perror(rp); return 1; }
    ROMIMG.resize(0x140000); size_t n = fread(ROMIMG.data(), 1, ROMIMG.size(), f); ROMIMG.resize(n); fclose(f); }
  FILE* sc = fopen(argv[1], "r"); if (!sc) { perror(argv[1]); return 1; }
  OUT = fopen(argv[2], "w");
  PinmameConfig c = { PINMAME_AUDIO_FORMAT_INT16, 44100, "", OnState, OnDisplayAvailable, OnDisplayUpdated, NULL, NULL, NULL, NULL, OnSol, NULL, IsKeyPressed, OnLog, NULL };
  char tmpl[] = "/tmp/hw_trace_XXXXXX"; char* dir = mkdtemp(tmpl);
  std::string roms = getenv("TRON_ROMS") ? getenv("TRON_ROMS") : std::string(getenv("HOME")) + "/.pinmame/roms";
  std::string cmd = std::string("mkdir -p ") + dir + "/nvram && ln -s " + roms + " " + dir + "/roms";
  if (system(cmd.c_str()) != 0) { fprintf(stderr, "setup failed\n"); return 1; }
  snprintf((char*)c.vpmPath, PINMAME_MAX_PATH, "%s/", dir);
  PinmameSetConfig(&c); PinmameSetHandleKeyboard(1); PinmameSetHandleMechanics(0); PinmameSetDmdMode(PINMAME_DMD_MODE_RAW);
  PinmameSetArmHook(hook);
  if (PinmameRun("trn_17402") != PINMAME_STATUS_OK) { fprintf(stderr, "run fail\n"); return 1; }
  while (!PinmameIsRunning()) std::this_thread::sleep_for(std::chrono::milliseconds(10));
  std::this_thread::sleep_for(std::chrono::milliseconds(500));
  while (emu() < 0.5) std::this_thread::sleep_for(std::chrono::milliseconds(2));
  { std::unique_lock<std::mutex> lk(gmu); target = emu() + 0.01; gateOn = true; }
  PinmameSetSwitch(41, 1); PinmameSetSwitch(53, 1);
  setTrough();
  step_to(8.0);
  emit("\"ev\":\"ready\",\"irq\":%llu", irqN);
  char line[512];
  while (fgets(line, sizeof line, sc)) {
    char* h = strchr(line, '#'); if (h) *h = 0;
    std::istringstream is(line); std::string cmd; if (!(is >> cmd)) continue;
    if (cmd == "wait") { double s; is >> s; step_to(emu() + s); }
    else if (cmd == "hit") { int sw; double ms = 60; is >> sw; is >> ms; emit("\"ev\":\"switch\",\"sw\":%d,\"ms\":%g", sw, ms);
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
    else if (cmd == "poke") { unsigned a, v, sz = 1; is >> std::hex >> a >> std::dec >> v >> sz; if (sz == 4) PinmameArmWrite32(a, v); else PinmameArmWrite8(a, v); emit("\"ev\":\"script\",\"what\":\"poke\",\"addr\":\"0x%x\",\"value\":%u", a, v); }
    else if (cmd == "button" || cmd == "key") {
      std::string b; double ms = 100; is >> b >> ms;
      int k = b == "left" ? PINMAME_KEYCODE_LEFT_SHIFT : b == "right" ? PINMAME_KEYCODE_RIGHT_SHIFT : b == "tilt" ? PINMAME_KEYCODE_INSERT
            : b == "tournament" ? PINMAME_KEYCODE_NUMBER_2 : b == "start" ? PINMAME_KEYCODE_NUMBER_1
            : b == "7" ? PINMAME_KEYCODE_NUMBER_7 : b == "8" ? PINMAME_KEYCODE_NUMBER_8 : b == "9" ? PINMAME_KEYCODE_NUMBER_9 : b == "0" ? PINMAME_KEYCODE_NUMBER_0
            : b == "end" ? PINMAME_KEYCODE_END : -1;
      if (k < 0) { fprintf(stderr, "unknown button %s\n", b.c_str()); continue; }
      emit("\"ev\":\"button\",\"button\":\"%s\",\"ms\":%g", b.c_str(), ms);
      if (ms < 0) keys[k] = 1; else if (ms == 0) keys[k] = 0; else { keys[k] = 1; step_to(emu() + ms / 1000.0); keys[k] = 0; step_to(emu() + 0.05); } }
    else if (cmd == "inject") { Inject j; std::string s; is >> s; j.addr = strtoul(s.c_str(), 0, 0);
      for (int i = 0; i < 4; i++) { j.a[i] = 0; if (is >> s) j.a[i] = strtoul(s.c_str(), 0, 0); }
      while (is >> s) j.stk.push_back(strtoul(s.c_str(), 0, 0));
      { std::lock_guard<std::mutex> g(injmu); injq.push_back(j); } }
    else if (cmd == "dump") dump_rules();
    else if (cmd == "mark") { std::string rest; std::getline(is, rest); emit("\"ev\":\"mark\",\"text\":\"%s\"", rest.c_str() + (rest.size() && rest[0] == ' ')); }
    else fprintf(stderr, "unknown command: %s\n", cmd.c_str());
  }
  step_to(emu() + 0.5);
  dump_rules();
  emit("\"ev\":\"end\",\"irq\":%llu", irqN);
  { std::unique_lock<std::mutex> lk(gmu); gateOn = false; gcv.notify_all(); }
  PinmameStop(); fclose(OUT); return 0;
}

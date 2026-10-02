#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <thread>
#include <chrono>
#include <vector>
#include <atomic>
#include "libpinmame.h"
extern "C" {
void PinmameSetArmHook(void (*h)(unsigned int, unsigned int*));
unsigned int PinmameArmRead32(unsigned int a);
unsigned int PinmameArmRead8(unsigned int a);
double PinmameEmuTime();
}
static FILE* LOG; static FILE* DMD;
static std::vector<int> force; static size_t forceIdx=0; static std::atomic<int> forceArmed{0};
static double nextForce=0, forceT=0; static int curForce=-1; static int injecting=0; static unsigned sv[16]; static unsigned injRet=0;
static unsigned r16(unsigned a){ return PinmameArmRead8(a) | (PinmameArmRead8(a+1)<<8); }
static void curdeff(unsigned &task, unsigned &did, unsigned &fn){ task=PinmameArmRead32(0x372c0); if(task){ did=r16(task+0x24); fn=PinmameArmRead32(task+4);} else {did=0;fn=0;} }
static void hook(unsigned pc, unsigned* r){
  if(curForce>=0 && !injecting && (pc==0x27830 || pc==0xb91c)){
    double t=PinmameEmuTime(); unsigned act=r16(0x381a8);
    if((t-forceT>0.3 && act!=(unsigned)curForce) || t-forceT>12.0){ fprintf(LOG,"%.4f FORCE_END %d active=%u\n",t,curForce,act); curForce=-1; nextForce=t+0.8; }
  }
  switch(pc){
  case 0x27b94: {
    double t=PinmameEmuTime();
    fprintf(LOG,"%.4f DEFF_START id=%u a=%u b=%u lr=%x\n",t,r[0],r[1],r[2],r[14]); break; }
  case 0xb91c: {
    double t=PinmameEmuTime();
    if(injecting){ if(r[13]==sv[13]){ for(int i=0;i<4;i++) r[i]=sv[i]; r[14]=sv[14]; injecting=0; fprintf(LOG,"%.4f INJECT_RET ret=%u\n",t,injRet);} break; }
    if(forceArmed && forceIdx<force.size() && curForce<0 && t>nextForce){
      curForce=force[forceIdx++]; forceT=t;
      for(int i=0;i<16;i++) sv[i]=r[i];
      r[0]=curForce; r[1]=0; r[2]=1; r[14]=0xb91c; r[15]=0x280b0; injecting=1;
      fprintf(LOG,"%.4f FORCE %d\n",t,curForce);
    }
    break; }
  case 0x282e0: fprintf(LOG,"%.4f DEFF_STOP id=%u lr=%x\n",PinmameEmuTime(),r[0],r[14]); break;
  case 0x2b378: case 0x2b424: case 0x2b210: { unsigned tk,d,f; curdeff(tk,d,f);
    fprintf(LOG,"%.4f IMG %x img=%u layer=%u x=%d y=%d task=%x deff=%u fn=%x lr=%x active=%u\n",PinmameEmuTime(),pc,r[0],r[1],(int)r[2],(int)r[3],tk,d,f,r[14],r16(0x381a8)); break; }
  case 0x2b194: case 0x2b2a0: { unsigned tk,d,f; curdeff(tk,d,f);
    fprintf(LOG,"%.4f DRAW rid=%u x=%d y=%d task=%x deff=%u fn=%x lr=%x active=%u\n",PinmameEmuTime(),r16(r[0]),(int)r[2],(int)r[3],tk,d,f,r[14],r16(0x381a8)); break; }
  case 0x27830: { unsigned tk,d,f; curdeff(tk,d,f); fprintf(LOG,"%.4f SHOW task=%x deff=%u active=%u\n",PinmameEmuTime(),tk,d,r16(0x381a8)); break; }
  case 0x2c744: { unsigned tk,d,f; curdeff(tk,d,f); fprintf(LOG,"%.4f SND call=%x deff=%u active=%u lr=%x\n",PinmameEmuTime(),r[0],d,r16(0x381a8),r[14]); break; }
  case 0x7cc: case 0x800: case 0x728: case 0x764: fprintf(LOG,"%.4f TUBE %x obj=%x rgb=%u/%u/%u ms=%u\n",PinmameEmuTime(),pc,r[0],PinmameArmRead32(r[1]),PinmameArmRead32(r[1]+4),PinmameArmRead32(r[1]+8),r[2]); break;
  case 0x7a0: fprintf(LOG,"%.4f TUBE %x obj=%x rgb=%u/%u/%u\n",PinmameEmuTime(),pc,r[0],r[1],r[2],r[3]); break;
  case 0x101b824: { unsigned tk,d,f; curdeff(tk,d,f); fprintf(LOG,"%.4f LEFF id=%u deff=%u lr=%x\n",PinmameEmuTime(),r[0],d,r[14]); break; }
  case 0x1011348: { unsigned tk=PinmameArmRead32(0x372c0); fprintf(LOG,"%.4f CLIP128 idx=%u\n",PinmameEmuTime(), tk? r16(tk+0x30):9999); break; }
  case 0x87ac: fprintf(LOG,"%.4f TASKFX id=%u lr=%x\n",PinmameEmuTime(),r[0],r[14]); break;
  case 0x79ec: fprintf(LOG,"%.4f EVENT %u\n",PinmameEmuTime(),r[0]); break;
  case 0x178c: fprintf(LOG,"%.4f AUDIT %u lr=%x\n",PinmameEmuTime(),r[0],r[14]); break;
  }
}
static unsigned char lastdmd[4096];
void PINMAMECALLBACK OnDisplayAvailable(int, int, PinmameDisplayLayout*, void*){}
void PINMAMECALLBACK OnDisplayUpdated(int index, void* p, PinmameDisplayLayout* L, void*){
  if(!p||L->width!=128||L->height!=32) return;
  if(memcmp(lastdmd,p,4096)==0) return; memcpy(lastdmd,p,4096);
  double t=PinmameEmuTime(); fwrite(&t,8,1,DMD); fwrite(p,1,4096,DMD);
}
static std::atomic<int> keys[128];
int PINMAMECALLBACK IsKeyPressed(PINMAME_KEYCODE k, void*){ return (int)k<128 ? keys[(int)k].load():0; }
void PINMAMECALLBACK OnState(int, void*){}
void PINMAMECALLBACK OnLog(PINMAME_LOG_LEVEL l, const char* f, va_list a, void*){ if(l==PINMAME_LOG_LEVEL_ERROR){vfprintf(stderr,f,a);fprintf(stderr,"\n");}}
static std::atomic<int> sol[64];
void PINMAMECALLBACK OnSol(PinmameSolenoidState* s, void*){ fprintf(LOG,"%.4f SOL %d %d\n",PinmameEmuTime(),s->solNo,s->state);}
static double emu(){ return PinmameEmuTime(); }
static void waitemu(double t){ while(emu()<t) std::this_thread::sleep_for(std::chrono::milliseconds(2)); }
int main(int argc,char**argv){
  const char* mode=argv[1]; double dur=atof(argv[2]);
  LOG=fopen(argv[3],"w"); DMD=fopen(argv[4],"wb");
  if(strncmp(mode,"sweep",5)&&strcmp(mode,"play")) for(int i=5;i<argc;i++) force.push_back(atoi(argv[i]));
  PinmameConfig c = { PINMAME_AUDIO_FORMAT_INT16, 44100, "", OnState, OnDisplayAvailable, OnDisplayUpdated, NULL, NULL, NULL, NULL, OnSol, NULL, IsKeyPressed, OnLog, NULL };
  snprintf((char*)c.vpmPath,PINMAME_MAX_PATH,"%s/.pinmame/",getenv("HOME"));
  PinmameSetConfig(&c); PinmameSetHandleKeyboard(1); PinmameSetHandleMechanics(0); PinmameSetDmdMode(PINMAME_DMD_MODE_RAW);
  PinmameSetArmHook(hook);
  if(PinmameRun("trn_174h")!=PINMAME_STATUS_OK){ fprintf(stderr,"run fail\n"); return 1; }
  while(!PinmameIsRunning()) std::this_thread::sleep_for(std::chrono::milliseconds(10));
  std::this_thread::sleep_for(std::chrono::milliseconds(500)); waitemu(0.5);
  for(int s:{18,19,20,21}) PinmameSetSwitch(s,1);
  waitemu(8);
  if(!strcmp(mode,"game")||!strcmp(mode,"sweep")){
    for(int k=0;k<4;k++){ waitemu(16+k); keys[PINMAME_KEYCODE_NUMBER_5]=1; waitemu(16.3+k); keys[PINMAME_KEYCODE_NUMBER_5]=0; }
    waitemu(20.5); keys[PINMAME_KEYCODE_NUMBER_1]=1; waitemu(20.8); keys[PINMAME_KEYCODE_NUMBER_1]=0;
  }

  if(!strcmp(mode,"play")){
    srand(atoi(argv[5]));
    struct Shot{std::vector<int> sw; int w;};
    std::vector<Shot> shots={
      {{35,37},10},{{38,34},10},{{43,44,44,44},7},{{46,36,36,36},8},{{39},6},{{41},6},
      {{49},4},{{50},4},{{51},4},{{1},3},{{2},3},{{3},3},{{4},3},{{7},2},{{8},2},{{13},2},{{48},2},
      {{25},2},{{28},2},{{14},2},{{12},3},{{30},4},{{31},4},{{32},4},{{26},4},{{27},4},{{11},5},{{44},2},{{36},2}};
    int tw=0; for(auto&x:shots) tw+=x.w;
    int trough=4; int inplay=0; int shooter=0; double shooterT=0; double lastEject=0; double lastSol1=0; int prevSol1=0, prevSol4=0, prevSol6=0, prevSol23=0;
    std::vector<double> drainAt; double nextShot=0; int scoop=0; double gameIdle=emu(); int bankUp=1; int recogPos=54; double recogT=0;
    auto setTrough=[&](){ for(int i=0;i<4;i++) PinmameSetSwitch(21-i, i<trough?1:0); };
    PinmameSetSwitch(53,1); PinmameSetSwitch(54,1); PinmameSetSwitch(41,1);
    auto startGame=[&](double t){ int np=1+rand()%2; fprintf(LOG,"%.4f PLAY start players=%d\n",t,np);
      for(int p=0;p<np;p++){ for(int k=0;k<4;k++){ waitemu(emu()+0.3); keys[PINMAME_KEYCODE_NUMBER_5]=1; waitemu(emu()+0.3); keys[PINMAME_KEYCODE_NUMBER_5]=0; } }
      waitemu(emu()+0.5); for(int p=0;p<np;p++){ keys[PINMAME_KEYCODE_NUMBER_1]=1; waitemu(emu()+0.3); keys[PINMAME_KEYCODE_NUMBER_1]=0; waitemu(emu()+0.6);} gameIdle=emu(); };
    double t0=emu(); startGame(t0);
    while(emu()<t0+dur){
      double t=emu();
      for(int q=1;q<=40;q++){ int v=PinmameGetSolenoid(q); if((v>0)!=(sol[q]>0)){ fprintf(LOG,"%.4f PSOL %d %d\n",t,q,v);} sol[q]=v; }
      int s1=sol[1]>0; if(s1 && !prevSol1 && trough>0){ trough--; setTrough(); inplay++; shooter=1; shooterT=t; PinmameSetSwitch(23,1); fprintf(LOG,"%.4f PLAY eject trough=%d inplay=%d\n",t,trough,inplay);
        drainAt.push_back(t+ 20+ (rand()%900)/10.0); }
      prevSol1=s1;
      if(shooter && t-shooterT>1.2){ PinmameSetSwitch(23,0); shooter=0; }
      int s4=sol[4]>0; if(s4 && !prevSol4 && scoop){ PinmameSetSwitch(11,0); scoop=0; } prevSol4=s4;
      int s6=sol[6]>0; if(s6 && !prevSol6){ recogT=t; } if(s6 && recogT>0 && t-recogT>0.6){ bankUp=!bankUp; PinmameSetSwitch(53,bankUp); PinmameSetSwitch(52,!bankUp); recogT=0; fprintf(LOG,"%.4f PLAY bank %s\n",t,bankUp?"up":"down"); } prevSol6=s6;
      int s23=sol[23]>0; static double rt=0; if(s23){ if(t-rt>0.5){ PinmameSetSwitch(recogPos,0); recogPos= recogPos==56?54:recogPos+1; PinmameSetSwitch(recogPos,1); rt=t; } }
      for(size_t i=0;i<drainAt.size();i++) if(t>drainAt[i] && !shooter && !scoop){ drainAt.erase(drainAt.begin()+i); inplay--; int ol=rand()%3; if(ol==0){int o=rand()%2?24:29; PinmameSetSwitch(o,1); waitemu(t+0.08); PinmameSetSwitch(o,0);} trough++; setTrough(); fprintf(LOG,"%.4f PLAY drain trough=%d inplay=%d\n",emu(),trough,inplay); break; }
      if(inplay>0 && !shooter && !scoop && t>nextShot){
        int r=rand()%tw; size_t k=0; for(;k<shots.size();k++){ r-=shots[k].w; if(r<0) break; }
        auto& sh=shots[k]; fprintf(LOG,"%.4f SWITCH %d\n",t,sh.sw[0]);
        for(int sw: sh.sw){ if(sw==11){ PinmameSetSwitch(11,1); scoop=1; waitemu(emu()+0.05); continue; }
          if(sw==41){ PinmameSetSwitch(41,0); waitemu(emu()+0.03); PinmameSetSwitch(41,1); waitemu(emu()+0.05); continue; }
          PinmameSetSwitch(sw,1); waitemu(emu()+0.06); PinmameSetSwitch(sw,0); waitemu(emu()+0.15); }
        nextShot=emu()+0.4+(rand()%150)/100.0;
      }
      if(scoop && sol[4]==0){ static double sc=0; if(sc==0) sc=t; if(t-sc>15){ PinmameSetSwitch(11,0); scoop=0; sc=0; } }
      if(inplay>0) gameIdle=t;
      if(inplay==0 && t-gameIdle>25){ startGame(t); }
      std::this_thread::sleep_for(std::chrono::milliseconds(2));
      fflush(LOG);
    }
    PinmameStop(); fclose(LOG); fclose(DMD); return 0;
  }
  nextForce=emu()+4; forceArmed=1;
  if(!strcmp(mode,"sweep")||!strcmp(mode,"sweepgame")){
    std::vector<int> sws; for(int i=6;i<argc;i++) sws.push_back(atoi(argv[i]));
    int reps=atoi(argv[5]);
    double t=emu()+3;
    for(int s: sws){ for(int k=0;k<reps;k++){ waitemu(t); fprintf(LOG,"%.4f SWITCH %d\n",emu(),s); PinmameSetSwitch(s, s==41?0:1); waitemu(t+0.08); PinmameSetSwitch(s, s==41?1:0); t+=2.5; } }
    waitemu(t+3); PinmameStop(); fclose(LOG); fclose(DMD); return 0;
  }
  double t0=emu(); double last=t0;
  while(emu()<t0+dur){
    if(!strcmp(mode,"game")){
      // simple ball sim: trough eject coil 1 -> open sw18 briefly, shooter -> launch
      static int ph=0; double t=emu();
      if(sol[1] && ph==0){ PinmameSetSwitch(18,0); ph=1; last=t; }
      if(ph==1 && t-last>0.5){ PinmameSetSwitch(18,1); ph=0; }
    }
    if(forceArmed && forceIdx>=force.size() && curForce<0 && emu()>nextForce) break;
    std::this_thread::sleep_for(std::chrono::milliseconds(5));
    fflush(LOG);
  }
  PinmameStop(); fclose(LOG); fclose(DMD); return 0;
}

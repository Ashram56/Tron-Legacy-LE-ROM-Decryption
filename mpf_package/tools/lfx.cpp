// Capture lamp-matrix light effects (leffs, table 0x040e23e4) from the real ROM.
// Starts a game, leaves the ball in the shooter lane, then starts each leff in turn
// (injected leff_start call) and logs only the lamps the leff itself owns.
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
void PinmameArmWrite8(unsigned int a, unsigned int d);
}
static FILE* LOG;
static std::vector<int> ids; static std::vector<int> pars; static size_t idx=0; static int curPar=-1;
static std::atomic<int> armed{0};
enum {IDLE, RUN, STOPPING};
static int st=IDLE, cur=0, injecting=0; static unsigned sv[16]; static double t0=0, nextT=0, lastSeen=0;
static const double CAP=12.0;
static unsigned r16(unsigned a){ return PinmameArmRead8(a)|(PinmameArmRead8(a+1)<<8); }
static unsigned char lastOut[30]; static int haveLast=0; static unsigned compCalls=0;
static int curLeff(){ unsigned tk=PinmameArmRead32(0x372c0); if(!tk) return 0; if(!(r16(tk+2)&0x20)) return 0; return r16(tk+0x28); }
static int taskAlive(int id){ for(unsigned tk=PinmameArmRead32(0x372b0); tk; tk=PinmameArmRead32(tk+0x1c)) if((r16(tk+2)&0x20)&&r16(tk+0x28)==(unsigned)id) return 1; return 0; }
static void sample(double t){
  unsigned char m[10]={0}, p[20]={0};
  // group-based leff region
  int gl=0; for(unsigned tk=PinmameArmRead32(0x372b0); tk; tk=PinmameArmRead32(tk+0x1c)) if((r16(tk+2)&0x20)&&r16(tk+0x28)==(unsigned)cur) gl=1;
  unsigned grp = r16(0x040e23ea + cur*12);
  if(gl && grp){ for(int i=0;i<10;i++){ unsigned char mk=PinmameArmRead8(0x3c238+i); m[i]|=mk; for(int pl=0;pl<2;pl++) p[pl*10+i]=(p[pl*10+i]&~mk)|(PinmameArmRead8(0x3c224+pl*10+i)&mk);} }
  for(unsigned L=PinmameArmRead32(0x3728c); L; L=PinmameArmRead32(L+0x24)){
    unsigned ow=PinmameArmRead32(L+0x20); if(!ow) continue;
    if(!((r16(ow+2)&0x20) && r16(ow+0x28)==(unsigned)cur)) continue;
    for(int i=0;i<10;i++){ unsigned char mk=PinmameArmRead8(L+0x14+i); m[i]|=mk; for(int pl=0;pl<2;pl++) p[pl*10+i]=(p[pl*10+i]&~mk)|(PinmameArmRead8(L+pl*10+i)&mk);} }
  unsigned char o[30]; memcpy(o,m,10); memcpy(o+10,p,20);
  if(haveLast && !memcmp(o,lastOut,30)) return; memcpy(lastOut,o,30); haveLast=1;
  fprintf(LOG,"%.4f F %d ",t,cur); for(int i=0;i<30;i++) fprintf(LOG,"%02x",o[i]); fprintf(LOG,"\n");
}
static void hook(unsigned pc, unsigned* r){
  switch(pc){
  case 0x7f68: { compCalls++; if(st!=IDLE){ double t=PinmameEmuTime(); sample(t);
      if(st==RUN){ int alive=taskAlive(cur); if(alive) lastSeen=t;
        if(!alive && t-t0>0.05){ fprintf(LOG,"%.4f END %d natural\n",t,cur); st=IDLE; haveLast=0; nextT=t+1.0; }
        else if(t-t0>CAP){ st=STOPPING; } } } break; }
  case 0xb91c: {
    double t=PinmameEmuTime();
    if(injecting){ if(r[13]==sv[13]){ if(st==RUN){ unsigned found=0; for(unsigned tk=PinmameArmRead32(0x372b0); tk; tk=PinmameArmRead32(tk+0x1c)) if((r16(tk+2)&0x20)&&r16(tk+0x28)==(unsigned)cur) found=tk;
            if(found && curPar>=0){ if(curPar>=0x10000) { PinmameArmWrite8(found+0x30,(curPar-0x10000)&0xff); PinmameArmWrite8(found+0x31,((curPar-0x10000)>>8)&0xff);} else PinmameArmWrite8(found+0x30,curPar); }
            fprintf(LOG,"%.4f RET %d %s par=%d\n",t,cur,found?"created":"refused",curPar); } for(int i=0;i<4;i++) r[i]=sv[i]; r[14]=sv[14]; injecting=0; if(st==STOPPING){ fprintf(LOG,"%.4f END %d cap\n",t,cur); st=IDLE; haveLast=0; nextT=t+1.0; } } break; }
    if(st==STOPPING){ for(int i=0;i<16;i++) sv[i]=r[i]; r[0]=cur; r[14]=0xb91c; r[15]=0xc404; injecting=1; break; }
    if(armed && st==IDLE && t>=nextT && idx<ids.size()){
      curPar=pars[idx]; cur=ids[idx++]; for(int i=0;i<16;i++) sv[i]=r[i]; r[0]=cur; r[14]=0xb91c; r[15]=0x87ac; injecting=1; st=RUN; t0=t; haveLast=0;
      fprintf(LOG,"%.4f BEGIN %d par=%d\n",t,cur,curPar);
    }
    break; }
  case 0x6970: case 0x69c0: { int l=curLeff(); if(l) fprintf(LOG,"%.4f COIL %d coil=%u ms=%u fn=%x\n",PinmameEmuTime(),l,r[0]&0xff,r[1]&0xffff,pc); break; }
  case 0x6b24: { int l=curLeff(); if(l) fprintf(LOG,"%.4f COILGRP %d grp=%u ms=%u\n",PinmameEmuTime(),l,r[0]&0xffff,r[1]&0xffff); break; }
  case 0x2c744: { int l=curLeff(); if(l) fprintf(LOG,"%.4f SND %d call=%x\n",PinmameEmuTime(),l,r[0]&0xffff); break; }
  case 0x10289b8: { int l=curLeff(); fprintf(LOG,"%.4f SHAKER %d a=%d b=%d lr=%x\n",PinmameEmuTime(),l,(int)r[0],(int)r[1],r[14]); break; }
  case 0x87ac: { if(!injecting || r[0]!=(unsigned)cur) fprintf(LOG,"%.4f LEFFSTART %u lr=%x inleff=%d\n",PinmameEmuTime(),r[0]&0xffff,r[14],curLeff()); break; }
  case 0x101b824: { int l=curLeff(); fprintf(LOG,"%.4f TUBE %u inleff=%d lr=%x\n",PinmameEmuTime(),r[0]&0xffff,l,r[14]); break; }
  case 0x280b0: { int l=curLeff(); if(l) fprintf(LOG,"%.4f DEFF %u inleff=%d\n",PinmameEmuTime(),r[0]&0xffff,l); break; }
  }
}
void PINMAMECALLBACK OnDisplayAvailable(int,int,PinmameDisplayLayout*,void*){}
void PINMAMECALLBACK OnDisplayUpdated(int,void*,PinmameDisplayLayout*,void*){}
static std::atomic<int> keys[128];
int PINMAMECALLBACK IsKeyPressed(PINMAME_KEYCODE k,void*){ return (int)k<128?keys[(int)k].load():0; }
void PINMAMECALLBACK OnState(int,void*){}
void PINMAMECALLBACK OnLog(PINMAME_LOG_LEVEL l,const char* f,va_list a,void*){ if(l==PINMAME_LOG_LEVEL_ERROR){vfprintf(stderr,f,a);fprintf(stderr,"\n");}}
void PINMAMECALLBACK OnSol(PinmameSolenoidState*,void*){}
static double emu(){ return PinmameEmuTime(); }
static void waitemu(double t){ while(emu()<t) std::this_thread::sleep_for(std::chrono::milliseconds(2)); }
int main(int argc,char**argv){
  LOG=fopen(argv[1],"w"); const char* mode=argv[2];
  for(int i=3;i<argc;i++){ char* c=strchr(argv[i],':'); ids.push_back(atoi(argv[i])); if(!c) pars.push_back(-1); else if(c[1]=='h') pars.push_back(0x10000+atoi(c+2)); else pars.push_back(atoi(c+2)); }
  PinmameConfig c={PINMAME_AUDIO_FORMAT_INT16,44100,"",OnState,OnDisplayAvailable,OnDisplayUpdated,NULL,NULL,NULL,NULL,OnSol,NULL,IsKeyPressed,OnLog,NULL};
  snprintf((char*)c.vpmPath,PINMAME_MAX_PATH,"%s/.pinmame/",getenv("HOME"));
  PinmameSetConfig(&c); PinmameSetHandleKeyboard(1); PinmameSetHandleMechanics(0); PinmameSetDmdMode(PINMAME_DMD_MODE_RAW);
  PinmameSetArmHook(hook);
  if(PinmameRun("trn_174h")!=PINMAME_STATUS_OK){ fprintf(stderr,"run fail\n"); return 1; }
  while(!PinmameIsRunning()) std::this_thread::sleep_for(std::chrono::milliseconds(10));
  waitemu(0.5); for(int s:{18,19,20,21}) PinmameSetSwitch(s,1); PinmameSetSwitch(53,1); PinmameSetSwitch(54,1); PinmameSetSwitch(41,1);
  waitemu(8);
  if(!strcmp(mode,"game")||!strcmp(mode,"pf")){
    for(int k=0;k<4;k++){ waitemu(9+k*0.6); keys[PINMAME_KEYCODE_NUMBER_5]=1; waitemu(9.3+k*0.6); keys[PINMAME_KEYCODE_NUMBER_5]=0; }
    waitemu(12); keys[PINMAME_KEYCODE_NUMBER_1]=1; waitemu(12.3); keys[PINMAME_KEYCODE_NUMBER_1]=0;
    int ej=0; double tEnd=emu()+8;
    while(emu()<tEnd){ if(!ej && PinmameGetSolenoid(1)>0){ ej=1; PinmameSetSwitch(21,0); PinmameSetSwitch(23,1); fprintf(LOG,"%.4f SIM eject\n",emu()); } std::this_thread::sleep_for(std::chrono::milliseconds(2)); }
  }
  if(!strcmp(mode,"pf")){ PinmameSetSwitch(23,0); waitemu(emu()+1.0); for(int sw:{35,37,26}){ PinmameSetSwitch(sw,1); waitemu(emu()+0.06); PinmameSetSwitch(sw,0); waitemu(emu()+0.5);} waitemu(emu()+3); fprintf(LOG,"%.4f SIM playfield validated\n",emu()); }
  fprintf(LOG,"%.4f READY comp=%u\n",emu(),compCalls);
  for(unsigned tk=PinmameArmRead32(0x372b0); tk; tk=PinmameArmRead32(tk+0x1c)) if(r16(tk+2)&0x20) fprintf(LOG,"RUNNING leff %u prio %u flags %x\n",r16(tk+0x28),PinmameArmRead8(tk+0x2a),r16(tk+0x2c));
  nextT=emu()+0.5; armed=1;
  while(true){ if(idx>=ids.size() && st==IDLE) break; std::this_thread::sleep_for(std::chrono::milliseconds(20)); fflush(LOG);
     }
  fprintf(LOG,"%.4f DONE comp=%u\n",emu(),compCalls);
  PinmameStop(); fclose(LOG); return 0;
}

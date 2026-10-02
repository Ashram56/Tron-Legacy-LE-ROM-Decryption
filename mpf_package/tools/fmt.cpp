// Calls the ROM's adjustment value formatters for given (fn, value) pairs and prints the text.
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <thread>
#include <chrono>
#include <vector>
#include <atomic>
#include "libpinmame.h"
extern "C" { void PinmameSetArmHook(void (*h)(unsigned int, unsigned int*)); unsigned int PinmameArmRead32(unsigned int a); unsigned int PinmameArmRead8(unsigned int a); void PinmameArmWrite8(unsigned int a, unsigned int d); double PinmameEmuTime(); }
struct J{unsigned fn; int v; int tag;}; static std::vector<J> jobs; static size_t idx=0; static std::atomic<int> armed{0}, done{0};
static int inj=0; static unsigned sv[16], buf=0, spx=0; static FILE* OUT;
static void hook(unsigned pc, unsigned* r){
  if(pc!=0xb91c) return;
  if(inj){ if(r[13]==spx){ char s[128]; int k=0; for(;k<127;k++){ s[k]=PinmameArmRead8(buf+k); if(!s[k]) break; } s[k]=0;
      fprintf(OUT,"%d\t%x\t%d\t%s\n",jobs[idx-1].tag,jobs[idx-1].fn,jobs[idx-1].v,s); fflush(OUT); for(int i=0;i<16;i++) r[i]=sv[i]; inj=0; } return; }
  if(!armed) return;
  if(idx>=jobs.size()){ done=1; return; }
  for(int i=0;i<16;i++) sv[i]=r[i];
  buf=0x3ee80; spx=0x3f400; for(int k=0;k<64;k++) PinmameArmWrite8(buf+k,0);
  r[0]=buf; r[1]=(unsigned)jobs[idx].v; r[13]=spx; r[14]=0xb91c; r[15]=jobs[idx].fn; idx++; inj=1;
}
void PINMAMECALLBACK OnDisplayAvailable(int,int,PinmameDisplayLayout*,void*){}
void PINMAMECALLBACK OnDisplayUpdated(int,void*,PinmameDisplayLayout*,void*){}
int PINMAMECALLBACK IsKeyPressed(PINMAME_KEYCODE,void*){ return 0; }
void PINMAMECALLBACK OnState(int,void*){}
void PINMAMECALLBACK OnLog(PINMAME_LOG_LEVEL,const char*,va_list,void*){}
int main(int argc,char**argv){
  FILE* in=fopen(argv[1],"r"); OUT=fopen(argv[2],"w"); unsigned fn; int v,tag; while(fscanf(in,"%d %x %d",&tag,&fn,&v)==3) jobs.push_back({fn,v,tag});
  PinmameConfig c={PINMAME_AUDIO_FORMAT_INT16,44100,"",OnState,OnDisplayAvailable,OnDisplayUpdated,NULL,NULL,NULL,NULL,NULL,NULL,IsKeyPressed,OnLog,NULL};
  snprintf((char*)c.vpmPath,PINMAME_MAX_PATH,"%s/.pinmame/",getenv("HOME"));
  PinmameSetConfig(&c); PinmameSetHandleKeyboard(0); PinmameSetHandleMechanics(0); PinmameSetArmHook(hook);
  if(PinmameRun("trn_174h")!=PINMAME_STATUS_OK) return 1;
  while(!PinmameIsRunning()) std::this_thread::sleep_for(std::chrono::milliseconds(10));
  while(PinmameEmuTime()<6) std::this_thread::sleep_for(std::chrono::milliseconds(10));
  armed=1; while(!done) std::this_thread::sleep_for(std::chrono::milliseconds(10));
  fclose(OUT); PinmameStop(); return 0;
}

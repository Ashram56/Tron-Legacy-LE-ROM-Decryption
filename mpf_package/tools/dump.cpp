#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <thread>
#include <chrono>
#include "libpinmame.h"
extern "C" { unsigned int PinmameArmRead32(unsigned int a); unsigned int PinmameArmRead8(unsigned int a); double PinmameEmuTime(); }
void PINMAMECALLBACK OnDisplayAvailable(int,int,PinmameDisplayLayout*,void*){}
void PINMAMECALLBACK OnDisplayUpdated(int,void*,PinmameDisplayLayout*,void*){}
int PINMAMECALLBACK IsKeyPressed(PINMAME_KEYCODE,void*){ return 0; }
void PINMAMECALLBACK OnState(int,void*){}
void PINMAMECALLBACK OnLog(PINMAME_LOG_LEVEL,const char*,va_list,void*){}
int main(int argc,char**argv){
  PinmameConfig c={PINMAME_AUDIO_FORMAT_INT16,44100,"",OnState,OnDisplayAvailable,OnDisplayUpdated,NULL,NULL,NULL,NULL,NULL,NULL,IsKeyPressed,OnLog,NULL};
  snprintf((char*)c.vpmPath,PINMAME_MAX_PATH,"%s/.pinmame/",getenv("HOME"));
  PinmameSetConfig(&c); PinmameSetHandleKeyboard(0); PinmameSetHandleMechanics(0);
  if(PinmameRun("trn_174h")!=PINMAME_STATUS_OK) return 1;
  while(!PinmameIsRunning()) std::this_thread::sleep_for(std::chrono::milliseconds(10));
  while(PinmameEmuTime()<atof(getenv("T")?getenv("T"):"6")) std::this_thread::sleep_for(std::chrono::milliseconds(10));
  FILE* f=fopen(argv[1],"wb");
  // dump ranges given as hex start/len pairs
  for(int i=2;i+1<argc;i+=2){ unsigned a=strtoul(argv[i],0,16), n=strtoul(argv[i+1],0,16); for(unsigned k=0;k<n;k++){ unsigned char b=PinmameArmRead8(a+k); fwrite(&b,1,1,f);} }
  fclose(f); PinmameStop(); return 0;
}

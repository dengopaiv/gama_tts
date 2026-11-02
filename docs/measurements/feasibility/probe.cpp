// Probe of libgamatts, used the way a C API would use it: one long-lived engine,
// many utterances, every exception caught and counted. A measuring tool for docs/09.
// Public domain, written 2026-11-02. It links libgamatts (GPL-3.0-or-later), so a built probe.exe is GPL.
#include <windows.h>
#include <psapi.h>
#undef min
#undef max
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <map>
#include <memory>
#include <random>
#include <string>
#include <thread>
#include <vector>
#include "Controller.h"
#include "Exception.h"
#include "Index.h"
#include "Model.h"
#include "TextParser.h"
#include "VTMControlModelConfiguration.h"
#include "VocalTractModel.h"
#include "VTMUtil.h"
#include "ConfigurationData.h"
using namespace GS;
using Clock = std::chrono::steady_clock;
static double ms(Clock::time_point a, Clock::time_point b){return std::chrono::duration<double,std::milli>(b-a).count();}

struct Engine {
  std::unique_ptr<Index> index; std::unique_ptr<VTMControlModel::Model> model;
  std::unique_ptr<VTMControlModel::Controller> ctl; std::unique_ptr<TextParser::TextParser> parser;
  double tLoad=0,tParser=0;
  explicit Engine(const std::string& dir){
    auto t0=Clock::now();
    index=std::make_unique<Index>(dir);
    model=std::make_unique<VTMControlModel::Model>(); model->load(*index);
    ctl=std::make_unique<VTMControlModel::Controller>(*index,*model);
    auto t1=Clock::now();
    parser=TextParser::TextParser::getInstance(*index,ctl->vtmControlModelConfiguration().phoStrFormat);
    auto t2=Clock::now(); tLoad=ms(t0,t1); tParser=ms(t1,t2);
  }
  void det(bool on){auto&c=ctl->vtmControlModelConfiguration(); c.randomIntonation=!on; c.intonationDrift=!on;}
  void tempo(double x){ctl->vtmControlModelConfiguration().tempo=x;}
  void pitch(double semis){auto&c=ctl->vtmControlModelConfiguration(); c.pitchOffset=base+semis;}
  double base=0; void capture(){base=ctl->vtmControlModelConfiguration().pitchOffset;}
};
static std::vector<std::string> readLines(const std::string& p){
  std::ifstream in(p,std::ios::binary); std::vector<std::string> v; std::string l;
  while(std::getline(in,l)){ if(!l.empty()&&l.back()=='\r') l.pop_back(); if(l.empty()||l[0]=='#') continue; v.push_back(l);} return v;}
struct Stat{int ok=0,fail=0,nan=0,silent=0; double audio=0,cpu=0,maxms=0; std::map<std::string,int> errs; std::vector<std::string> sample;};
static std::string shortMsg(std::string m){ for(auto&c:m) if(c=='\n'||c=='\r') c=' '; auto p=m.find("Pronunciation not found"); if(p!=std::string::npos) return "Pronunciation not found"; p=m.find(" at index="); if(p!=std::string::npos) m=m.substr(0,p); if(m.size()>90) m=m.substr(0,90); return m;}
static void runOne(Engine&e,const std::string& text,Stat&s,std::vector<float>*keep=nullptr){
  std::vector<float> buf;
  auto t0=Clock::now();
  try{
    std::string ph=e.parser->parse((text+" ").c_str());
    e.ctl->synthesizePhoneticStringToBuffer(ph,nullptr,buf);
    auto t1=Clock::now(); double c=ms(t0,t1); s.cpu+=c; if(c>s.maxms)s.maxms=c;
    bool nan=false; float pk=0; for(float x:buf){ if(!std::isfinite(x)) nan=true; else if(std::fabs(x)>pk) pk=std::fabs(x);}
    if(nan) s.nan++; if(buf.empty()||pk==0.f) s.silent++;
    s.audio+=buf.size()/e.ctl->outputSampleRate(); s.ok++;
    if(keep)*keep=std::move(buf);
  }catch(const std::exception& ex){ s.fail++; s.errs[shortMsg(ex.what())]++; if(s.sample.size()<4) s.sample.push_back(text.substr(0,60)); }
  catch(...){ s.fail++; s.errs["(unknown exception)"]++; }
}
static void printStat(const char* tag,const Stat&s){
  std::printf("%-22s ok=%4d fail=%4d nan=%d silent=%d audio=%7.1fs cpu=%8.0fms rtf=%6.1f maxUtt=%6.0fms\n",tag,s.ok,s.fail,s.nan,s.silent,s.audio,s.cpu,s.cpu>0?s.audio*1000/s.cpu:0,s.maxms);
  for(auto&kv:s.errs) std::printf("    %4d x %s\n",kv.second,kv.first.c_str());
  for(auto&x:s.sample) std::printf("      e.g. [%s]\n",x.c_str());
  std::fflush(stdout);
}
static void writeWav(const std::string& p,const std::vector<float>& b,int rate){
  std::ofstream o(p,std::ios::binary); uint32_t n=(uint32_t)b.size()*2; uint32_t v; uint16_t h;
  o.write("RIFF",4); v=36+n; o.write((char*)&v,4); o.write("WAVEfmt ",8); v=16; o.write((char*)&v,4); h=1; o.write((char*)&h,2); h=1; o.write((char*)&h,2);
  v=rate; o.write((char*)&v,4); v=rate*2; o.write((char*)&v,4); h=2; o.write((char*)&h,2); h=16; o.write((char*)&h,2); o.write("data",4); o.write((char*)&n,4);
  for(float x:b){ int16_t s=(int16_t)std::lrint(std::fmax(-1.f,std::fmin(1.f,x))*32767.f); o.write((char*)&s,2);} }
static double rssMB(){PROCESS_MEMORY_COUNTERS c; GetProcessMemoryInfo(GetCurrentProcess(),&c,sizeof c); return c.WorkingSetSize/1048576.0;}

int main(int argc,char**argv){
  if(argc<3){std::puts("cmd root ...");return 2;}
  std::string cmd=argv[1], root=argv[2]; root+="/voice/english/";
  // The dictionary loader writes 45 "Duplicate word" lines to stderr; drop them so output stays readable.
  if(!getenv("PROBE_STDERR")) freopen("NUL","w",stderr);
  if(cmd=="load"){ // per-voice load times; second of two loads so the file cache is warm
    for(int i=3;i<argc;i++){ for(int r=0;r<2;r++){ Engine e(root+argv[i]); e.capture();
      if(r==1){ std::printf("%-16s rate=%6.0f int=%8.1f load(model+ctl)=%6.1fms parser+dict=%6.1fms variant=%s period=%u pitchOff=%g\n",argv[i],e.ctl->outputSampleRate(),e.ctl->vtmInternalSampleRate(),e.tLoad,e.tParser,e.ctl->vtmControlModelConfiguration().variantName.c_str(),e.ctl->vtmControlModelConfiguration().controlPeriod,e.ctl->vtmControlModelConfiguration().pitchOffset);} }
    } std::printf("rss=%.1f MB\n",rssMB());
  } else if(cmd=="corpus"){ // corpus root voice file tempo pitch det
    Engine e(root+argv[3]); e.capture(); auto L=readLines(argv[4]); double tempo=atof(argv[5]),p=atof(argv[6]); bool d=argc>7&&atoi(argv[7]);
    e.tempo(tempo); e.pitch(p); e.det(d); Stat s; for(auto&l:L) runOne(e,l,s); char tag[64]; snprintf(tag,64,"%s t=%.2f p=%+.0f",argv[3],tempo,p); printStat(tag,s);
  } else if(cmd=="sweep"){ // sweep root voice file t1 t2 ...
    Engine e(root+argv[3]); e.capture(); auto L=readLines(argv[4]); e.det(true);
    for(int i=5;i<argc;i++){ double t=atof(argv[i]); e.tempo(t); Stat s; for(auto&l:L) runOne(e,l,s); char tag[64]; snprintf(tag,64,"%s t=%.2f",argv[3],t); printStat(tag,s);}
  } else if(cmd=="pitchsweep"){
    Engine e(root+argv[3]); e.capture(); auto L=readLines(argv[4]); e.det(true);
    for(int i=5;i<argc;i++){ double p=atof(argv[i]); e.pitch(p); Stat s; for(auto&l:L) runOne(e,l,s); char tag[64]; snprintf(tag,64,"%s p=%+.0f",argv[3],p); printStat(tag,s);}
  } else if(cmd=="fuzz"){ // fuzz root voice seed n mode(0=ascii printable,1=any bytes,2=screen-reader fragments) lastfile
    Engine e(root+argv[3]); unsigned seed=atoi(argv[4]); int n=atoi(argv[5]); int mode=atoi(argv[6]); std::mt19937 g(seed);
    std::ofstream lastf(argv[7]); Stat s; const char* frag[]={"Button","a","I","1","1.5","$3","%","@","#","/","\\","(","*","--","...","e.g.","Mr.","www.example.com","C:\\Windows","x86_64","3/4","10:30","'","\"","A","B","Z","?","!",";",":",",","the","of","Alt+F4","blank","unlabelled","heading level 2","R2D2","iOS","NVDA","co-op","naive","1st","22nd","100%","-5","+7","0","0.","1,000,000","1e9","Ctrl","_","~","^","&","=","<",">","[","]","{","}","|","`"};
    for(int i=0;i<n;i++){ std::string t; int len=1+g()%40; if(mode==2){ int w=1+g()%8; for(int k=0;k<w;k++){ t+=frag[g()%(sizeof frag/sizeof*frag)]; if(g()%3) t+=' ';} } else for(int k=0;k<len;k++){ if(mode==0) t+=(char)(32+g()%95); else { char c=(char)(1+g()%255); t+=c; } }
      lastf.seekp(0); std::string hex; for(unsigned char c:t){ char h[4]; snprintf(h,4,"%02x",c); hex+=h; } lastf<<i<<" "<<hex<<"\n"<<std::string(128,' ')<<std::flush; runOne(e,t,s); }
    char tag[64]; snprintf(tag,64,"fuzz mode=%d %s",mode,argv[3]); printStat(tag,s);
  } else if(cmd=="repeat"){ // the same text, same engine, repeatedly: identical? and against a fresh engine?
    Engine e(root+argv[3]); e.det(true); std::string t=argv[4]; Stat s; std::vector<float> a,b,c; runOne(e,t,s,&a); runOne(e,t,s,&b); Engine f(root+argv[3]); f.det(true); runOne(f,t,s,&c);
    auto diff=[](auto&x,auto&y){ if(x.size()!=y.size()) return (double)-1; double m=0; for(size_t i=0;i<x.size();i++) m=std::fmax(m,std::fabs(x[i]-y[i])); return m;};
    std::printf("%s samples=%zu same-engine maxdiff=%g fresh-vs-first maxdiff=%g\n",argv[3],a.size(),diff(a,b),diff(a,c));
  } else if(cmd=="threads"){ // two engines concurrently against a sequential reference
    std::string v=argv[3]; auto L=readLines(argv[4]); if(L.size()>60) L.resize(60);
    auto all=[&](std::vector<std::vector<float>>&out){ Engine e(root+v); e.det(true); Stat s; for(auto&l:L){ std::vector<float> b; runOne(e,l,s,&b); out.push_back(std::move(b)); } };
    std::vector<std::vector<float>> ref,a,b; all(ref); std::thread t1([&]{all(a);}),t2([&]{all(b);}); t1.join(); t2.join();
    int bad=0; for(size_t i=0;i<ref.size();i++) if(ref[i]!=a[i]||ref[i]!=b[i]) bad++; std::printf("%s threads: %zu utterances, %d differ from sequential\n",v.c_str(),ref.size(),bad);
  } else if(cmd=="leak"){ // long-run memory
    Engine e(root+argv[3]); auto L=readLines(argv[4]); e.det(false); Stat s; int rounds=atoi(argv[5]); for(int r=0;r<rounds;r++){ for(auto&l:L) runOne(e,l,s); if(r==0||r==rounds-1||r%5==0) std::printf("round %3d rss=%.1f MB\n",r,rssMB()); } printStat(argv[3],s);
  } else if(cmd=="wav"){ // wav root voice out tempo pitch det text
    Engine e(root+argv[3]); e.capture(); e.tempo(atof(argv[5])); e.pitch(atof(argv[6])); e.det(atoi(argv[7])); Stat s; std::vector<float> b; runOne(e,argv[8],s,&b); if(s.fail){ printStat("wav",s); return 1;} writeWav(argv[4],b,(int)e.ctl->outputSampleRate()); std::printf("%s %zu samples %.3f s\n",argv[3],b.size(),b.size()/e.ctl->outputSampleRate());
  } else if(cmd=="ph"){ Engine e(root+argv[3]); std::cout<<e.parser->parse((std::string(argv[4])+" ").c_str())<<"\n";
  } else if(cmd=="wavs"){ // wavs root voice dir tempo pitch det file: one wav per corpus line, numbered
    Engine e(root+argv[3]); e.capture(); e.tempo(atof(argv[5])); e.pitch(atof(argv[6])); e.det(atoi(argv[7])); auto L=readLines(argv[8]); int i=0; for(auto&l:L){ Stat s; std::vector<float> b; runOne(e,l,s,&b); char n[512]; snprintf(n,512,"%s/%03d.wav",argv[4],i++); if(!s.fail) writeWav(n,b,(int)e.ctl->outputSampleRate()); }
  } else if(cmd=="lines"){ // lines root voice file tempo pitch: one line per utterance, flushed first, so a crash names its input
    Engine e(root+argv[3]); e.capture(); auto L=readLines(argv[4]); e.det(argc>7?atoi(argv[7]):1); e.tempo(atof(argv[5])); e.pitch(atof(argv[6])); int i=0;
    for(auto&l:L){ std::printf("%3d [%s] ",i++,l.substr(0,70).c_str()); std::fflush(stdout); Stat s; std::vector<float> b; runOne(e,l,s,&b); float pk=0; for(float x:b) pk=std::fmax(pk,std::fabs(x)); std::printf("%s n=%zu dur=%.3f pk=%.3f\n",s.fail?"FAIL":"ok",b.size(),b.size()/e.ctl->outputSampleRate(),pk); for(auto&kv:s.errs) std::printf("   %s\n",kv.first.c_str()); std::fflush(stdout);}
  } else if(cmd=="dump"){ // dump root voice text tempo: intonation points, events and the pitch track
    Engine e(root+argv[3]); e.capture(); e.det(true); e.tempo(atof(argv[5])); std::string ph=e.parser->parse((std::string(argv[4])+" ").c_str()); std::printf("ph=%s\n",ph.c_str());
    e.ctl->synthesizePhoneticStringToFile(ph,nullptr,nullptr); auto& el=e.ctl->eventList();
    for(auto& ip:el.intonationPoints()) std::printf("point abs=%.2f beat=%.2f semitone=%.3f slope=%.4f rule=%d\n",ip.absoluteTime(),ip.beatTime(),ip.semitone(),ip.slope(),ip.ruleIndex());
    int n=0; for(auto& ev:el.list()){ if(ev->interpData) std::printf("event#%d t=%d interp a=%.5g b=%.5g c=%.5g d=%.5g\n",n,ev->time,ev->interpData->a,ev->interpData->b,ev->interpData->c,ev->interpData->d); n++; } std::printf("events=%d lastT=%d\n",n,el.list().back()->time);
    int f=0; for(auto& fr:e.ctl->vtmParameterList()){ std::printf("%d:%.1f ",f*4,fr[0]); if(++f%10==0) std::printf("\n"); } std::printf("\n");
  } else if(cmd=="ownloop"){ // ownloop root voice text: can a wrapper own the tube, with the engine unchanged?
    Engine e(root+argv[3]); e.det(true); std::string ph=e.parser->parse((std::string(argv[4])+" ").c_str());
    std::vector<float> ref; e.ctl->synthesizePhoneticStringToBuffer(ph,nullptr,ref);
    // the track only (a null output file skips the tube), then a tube of our own over a ConfigurationData of our own
    e.ctl->synthesizePhoneticStringToFile(ph,nullptr,nullptr); std::vector<std::vector<float>> track=e.ctl->vtmParameterList();
    auto render=[&](ConfigurationData& d,std::vector<float>& out,double& ctor){ auto t0=Clock::now(); auto vtm=VTM::VocalTractModel::getInstance(d); ctor=ms(t0,Clock::now());
      auto list=track; list.push_back(list.back()); const unsigned steps=(unsigned)std::rint(vtm->internalSampleRate()/e.ctl->vtmControlModelConfiguration().controlRate); const float coef=1.0f/steps; size_t np=track[0].size(); std::vector<float> cur(np),del(np);
      for(size_t i=1;i<list.size();i++){ for(size_t j=0;j<np;j++){ cur[j]=list[i-1][j]; del[j]=(list[i][j]-cur[j])*coef; } for(unsigned j=0;j<steps;j++){ vtm->setAllParameters(cur); vtm->execSynthesisStep(); for(size_t k=0;k<np;k++) cur[k]+=del[k]; } }
      vtm->finishSynthesis(); const auto& a=vtm->outputBuffer(); float sc=VTM::Util::calculateOutputScale(a); out.resize(a.size()); for(size_t i=0;i<a.size();i++) out[i]=a[i]*sc; };
    ConfigurationData d(e.index->entry("vtm_file")); d.insert(*e.ctl->vtmControlModelConfiguration().variantData);
    std::vector<float> o1,o2; double c1=0,c2=0; render(d,o1,c1); std::printf("own tube, same config: samples %zu vs %zu, identical=%d, tube ctor %.2f ms\n",o1.size(),ref.size(),(int)(o1==ref),c1);
    d.put("breathiness",25.0); d.put("vocal_tract_length",16.0); auto t0=Clock::now(); render(d,o2,c2); double whole=ms(t0,Clock::now()); std::printf("own tube, breathiness 25 and tract 16 cm: samples %zu, differs=%d, tube ctor %.2f ms, whole render %.1f ms\n",o2.size(),(int)(o2!=ref),c2,whole);
    // pitch offset reference is read from the controller's data each utterance
    e.ctl->vtmConfigData().put("reference_glottal_pitch",-6.0); e.ctl->synthesizePhoneticStringToFile(ph,nullptr,nullptr); std::printf("controller reference_glottal_pitch -6: first track pitch moved %.2f -> %.2f\n",track[50][0],e.ctl->vtmParameterList()[50][0]);
    // an exception on one utterance must leave the next one intact
    Stat s; try{ e.parser->parse("* "); }catch(...){ std::puts("parse of '*' threw, as expected"); } e.ctl->vtmConfigData().put("reference_glottal_pitch",-12.0); e.tempo(10.0); int threw=0; for(auto w:{"Muscle, muscular; goal and iron;","Golf, wolf; countenants; lieutenants"}){ try{ auto p=e.parser->parse(w); std::vector<float> b; e.ctl->synthesizePhoneticStringToBuffer(p,nullptr,b);}catch(...){threw++;} } e.tempo(1.0); std::vector<float> after; e.ctl->synthesizePhoneticStringToBuffer(ph,nullptr,after); std::printf("after %d engine exceptions, next utterance identical=%d\n",threw,(int)(after==ref));
  } else if(cmd=="wavcfg"){ // wavcfg root voice out text: the configuration exactly as the data files say, nothing overridden
    Engine e(root+argv[3]); Stat s; std::vector<float> b; runOne(e,argv[5],s,&b); if(s.fail){ printStat("wavcfg",s); return 1;} writeWav(argv[4],b,(int)e.ctl->outputSampleRate()); std::printf("%zu samples\n",b.size());
  } else if(cmd=="track"){ // track root voice file rounds det t1 t2 ...: rule engine only, no tube. Non-finite and out-of-range values per tempo.
    Engine e(root+argv[3]); e.capture(); auto L=readLines(argv[4]); int rounds=atoi(argv[5]); e.det(atoi(argv[6]));
    const auto& P=e.model->parameterList();
    std::printf("params:"); for(size_t k=0;k<P.size();k++) std::printf(" %s[%g,%g]",P[k].name().c_str(),P[k].minimum(),P[k].maximum()); std::printf("\n");
    for(int i=7;i<argc;i++){ double t=atof(argv[i]); e.tempo(t);
      int utt=0,badUtt=0,hiUtt=0,fail=0; long frames=0,nonfinite=0; double pmin=1e30,pmax=-1e30; std::map<std::string,int> byParam; std::vector<std::string> ex;
      for(int r=0;r<rounds;r++) for(auto&l:L){ try{ std::string ph=e.parser->parse((l+" ").c_str()); e.ctl->synthesizePhoneticStringToFile(ph,nullptr,nullptr); }catch(const std::exception&){ fail++; continue; }
        utt++; bool bad=false,hi=false; for(auto&fr:e.ctl->vtmParameterList()){ frames++; for(size_t k=0;k<fr.size();k++){ double v=fr[k]; if(!std::isfinite(v)){ nonfinite++; bad=true; byParam[P[k].name()]++; } else if(k==0){ pmin=std::min(pmin,v); pmax=std::max(pmax,v); if(v>30||v<-60) hi=true; } } }
        if(bad) badUtt++; if(hi) hiUtt++; if((bad||hi)&&ex.size()<6&&std::find(ex.begin(),ex.end(),l)==ex.end()) ex.push_back(l); }
      std::printf("t=%5.2f utt=%5d exc=%4d badUtt=%4d wildPitchUtt=%4d frames=%7ld nonfinite=%7ld pitch=[%.1f, %.1f]",t,utt,fail,badUtt,hiUtt,frames,nonfinite,pmin,pmax); for(auto&kv:byParam) std::printf(" %s:%d",kv.first.c_str(),kv.second); std::printf("\n"); for(auto&x:ex) std::printf("     e.g. [%s]\n",x.substr(0,50).c_str()); std::fflush(stdout); }
  } else { std::puts("unknown"); return 2; }
  return 0;
}

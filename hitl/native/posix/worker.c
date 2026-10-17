/* Fixed-step worker. POSIX; the clock, sleep and real-time policy are per platform (macOS: mach time and the
   time-constraint policy; Linux: CLOCK_MONOTONIC and SCHED_FIFO, which needs a privilege and otherwise reports
   its errno through hil_worker_policy_status). */
#include "hil_model_api.h"
#include <pthread.h>
#ifdef __APPLE__
#include <mach/mach_time.h>
#include <mach/thread_policy.h>
#include <mach/mach.h>
#else
#include <sched.h>
#include <time.h>
#endif
#include <stdint.h>
#include <string.h>
#define EXPORT __attribute__((visibility("default")))
#define TRACE_CAPACITY 8192
typedef int32_t (*Step)(const HilModelInput*,HilModelOutput*);
typedef struct {uint64_t index,duration_ns,lateness_ns; int64_t lag_ns;} Trace;
typedef struct {HilModelOutput output; uint64_t produced,misses,max_lateness_ns,max_step_ns,start_ns,now_ns; int32_t running,fault;} Snapshot;
static pthread_mutex_t lock=PTHREAD_MUTEX_INITIALIZER;
static pthread_t thread;
static int started,stop_requested;
static HilModelInput input;
static Snapshot snapshot;
static Trace traces[TRACE_CAPACITY];
static uint64_t trace_read,trace_write,late_limit;
typedef struct {uint64_t previous_begin_ns,previous_end_ns,publish_begin_ns,publish_end_ns,deadline_ns,wake_ns,fault_index;} WorkerDiagnostic;
static WorkerDiagnostic diagnostic;
EXPORT void hil_worker_diagnostics(WorkerDiagnostic*out){pthread_mutex_lock(&lock);*out=diagnostic;pthread_mutex_unlock(&lock);}
static Step step;
static int qos_result=-1,policy_result=-1;
EXPORT int hil_worker_policy_status(void){return policy_result;}
EXPORT int hil_worker_qos_status(void){return qos_result;}
#ifdef __APPLE__
static mach_timebase_info_data_t tb;
static pthread_once_t clock_once=PTHREAD_ONCE_INIT;
static void initialize_clock(void){mach_timebase_info(&tb);}
EXPORT uint64_t hil_worker_now_ns(void) {pthread_once(&clock_once,initialize_clock);return (uint64_t)((long double)mach_absolute_time()*tb.numer/tb.denom);}
static void set_policy(void){
 qos_result=pthread_set_qos_class_self_np(QOS_CLASS_USER_INTERACTIVE,0);
 pthread_once(&clock_once,initialize_clock);
 thread_time_constraint_policy_data_t policy;
 policy.period=(uint32_t)((long double)4000000*tb.denom/tb.numer);
 policy.computation=(uint32_t)((long double)1000000*tb.denom/tb.numer);
 policy.constraint=(uint32_t)((long double)2000000*tb.denom/tb.numer);policy.preemptible=1;
 thread_t port=mach_thread_self();policy_result=thread_policy_set(port,THREAD_TIME_CONSTRAINT_POLICY,(thread_policy_t)&policy,THREAD_TIME_CONSTRAINT_POLICY_COUNT);mach_port_deallocate(mach_task_self(),port);
}
static void wait_until_ns(uint64_t deadline){mach_wait_until((uint64_t)((long double)deadline*tb.denom/tb.numer));}
#else
EXPORT uint64_t hil_worker_now_ns(void) {struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return (uint64_t)t.tv_sec*1000000000ull+(uint64_t)t.tv_nsec;}
static void set_policy(void){
 struct sched_param param={.sched_priority=sched_get_priority_min(SCHED_FIFO)+1};
 qos_result=0;policy_result=pthread_setschedparam(pthread_self(),SCHED_FIFO,&param);
}
static void wait_until_ns(uint64_t deadline){
 struct timespec t={.tv_sec=(time_t)(deadline/1000000000ull),.tv_nsec=(long)(deadline%1000000000ull)};
 while(clock_nanosleep(CLOCK_MONOTONIC,TIMER_ABSTIME,&t,NULL)!=0){}
}
#endif
extern int hil_io_publish(const HilModelOutput*);
static void *run(void *unused) {
 (void)unused;
 set_policy();
 uint64_t start=hil_worker_now_ns(),k=0,consumed_sequence=0;
 pthread_mutex_lock(&lock);snapshot.start_ns=start;snapshot.running=1;pthread_mutex_unlock(&lock);
 for(;;) {
  uint64_t deadline=start+k*4000000;
  wait_until_ns(deadline);
  uint64_t begin=hil_worker_now_ns(),late=begin>deadline?begin-deadline:0;
  HilModelInput current; HilModelOutput output={.abi_version=HIL_ABI_VERSION,.struct_size=sizeof(HilModelOutput)};
  pthread_mutex_lock(&lock);
  if(stop_requested) {pthread_mutex_unlock(&lock);break;}
  if(late>=late_limit) {diagnostic.deadline_ns=deadline;diagnostic.wake_ns=begin;diagnostic.fault_index=k;snapshot.fault=5;snapshot.now_ns=begin;snapshot.misses++;if(late>snapshot.max_lateness_ns)snapshot.max_lateness_ns=late;if(trace_write-trace_read<TRACE_CAPACITY)traces[trace_write++%TRACE_CAPACITY]=(Trace){k,0,late,(int64_t)late};pthread_mutex_unlock(&lock);break;}
  current=input;current.step_index=k;
  current.actuator_new=current.actuator_valid && current.input_sequence!=consumed_sequence;
  if(current.actuator_new)consumed_sequence=current.input_sequence;
  if(current.actuator_valid) current.actuator_age_ns=begin>=current.actuator_age_ns?begin-current.actuator_age_ns:0;
  input.actuator_new=0;
  if((current.actuator_valid && current.actuator_age_ns>=2000000000)||(!current.actuator_valid&&k>1250)) {snapshot.fault=7;pthread_mutex_unlock(&lock);break;}
  pthread_mutex_unlock(&lock);
  int32_t code=step(&current,&output);uint64_t end=hil_worker_now_ns();
  pthread_mutex_lock(&lock);
  if(trace_write-trace_read>=TRACE_CAPACITY) {snapshot.fault=6;pthread_mutex_unlock(&lock);break;}
  traces[trace_write++%TRACE_CAPACITY]=(Trace){k,end-begin,late,(int64_t)(end-(start+k*4000000))};
  snapshot.now_ns=end;if(late>=4000000)snapshot.misses++;
  if(late>snapshot.max_lateness_ns)snapshot.max_lateness_ns=late;
  if(end-begin>snapshot.max_step_ns)snapshot.max_step_ns=end-begin;
  if(code) {snapshot.fault=code;pthread_mutex_unlock(&lock);break;}
  snapshot.output=output;snapshot.produced=++k;diagnostic.previous_begin_ns=begin;diagnostic.previous_end_ns=end;
  pthread_mutex_unlock(&lock);
  uint64_t publish_begin=hil_worker_now_ns();int io_fault=hil_io_publish(&output);uint64_t publish_end=hil_worker_now_ns();
  pthread_mutex_lock(&lock);diagnostic.publish_begin_ns=publish_begin;diagnostic.publish_end_ns=publish_end;pthread_mutex_unlock(&lock);
  if(io_fault){pthread_mutex_lock(&lock);diagnostic.deadline_ns=deadline;diagnostic.wake_ns=begin;diagnostic.fault_index=k-1;snapshot.fault=io_fault;pthread_mutex_unlock(&lock);break;}
 }
 pthread_mutex_lock(&lock);snapshot.running=0;pthread_mutex_unlock(&lock);return NULL;
}
EXPORT int hil_worker_start(void *function,const HilModelInput *initial,uint64_t limit) {
 if(started||!function||!initial||limit<4000000) return 2;
 step=(Step)function;input=*initial;late_limit=limit;stop_requested=0;
 memset(&snapshot,0,sizeof(snapshot));memset(&diagnostic,0,sizeof(diagnostic));trace_read=trace_write=0;started=1;
 if(pthread_create(&thread,NULL,run,NULL)) {started=0;return 3;}return 0;
}
EXPORT void hil_worker_input(const HilModelInput *value) {pthread_mutex_lock(&lock);input=*value;pthread_mutex_unlock(&lock);}
EXPORT void hil_worker_snapshot(Snapshot *out) {pthread_mutex_lock(&lock);*out=snapshot;pthread_mutex_unlock(&lock);}
EXPORT uint32_t hil_worker_drain(Trace *out,uint32_t capacity) {
 pthread_mutex_lock(&lock);uint32_t n=0;
 while(trace_read<trace_write&&n<capacity)out[n++]=traces[trace_read++%TRACE_CAPACITY];
 pthread_mutex_unlock(&lock);return n;
}
EXPORT void hil_worker_stop(void) {if(!started)return;pthread_mutex_lock(&lock);stop_requested=1;pthread_mutex_unlock(&lock);pthread_join(thread,NULL);started=0;}

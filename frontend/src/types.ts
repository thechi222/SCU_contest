export type Kind='asr'|'upscale';
export type Status='queued'|'loading'|'running'|'retrying'|'completed'|'failed'|'cancelled';
export type User={id:string;username:string;display_name:string;role:'admin'|'member';enabled:number;max_running:number;daily_limit:number};
export type Artifact={id:string;name:string;media_type:string;size:number};
export type Attempt={id:string;node_id:string;node_name:string;gpu_name:string;started_at:number;ended_at:number|null;outcome:string|null;error:string|null;gpu_verified:number;metrics:Record<string,unknown>};
export type Job={id:string;batch_id:string;batch_name:string;is_demo:number;user_id:string;owner_name:string;kind:Kind;filename:string;input_bytes:number;status:Status;attempt_count:number;stage:string;progress:number|null;error:string|null;created_at:number;completed_at:number|null;artifacts:Artifact[];attempts:Attempt[];waiting_reason?:string};
export type Node={id:string;owner_id:string;name:string;gpu_name:string;memory_mb:number;sharing:number;local_enabled:number;revoked:number;online:boolean;within_schedule:boolean;capabilities:Record<string,{profile:string;cuda_verified:boolean;peak_vram_mb:number}>;environment?:Record<string,unknown>;telemetry:{gpu_utilization?:number|null;memory_used_mb?:number|null;memory_free_mb?:number|null;temperature_c?:number|null;power_w?:number|null;on_ac?:boolean|null};schedule_start?:string|null;schedule_end?:string|null;utc_offset_minutes:number;last_seen:number;current_job:null|{job_id?:string;kind:Kind;status:Status;stage:string};completed_count:number;compute_seconds:number;owner_name?:string};
export type Event={id:number;kind:string;message:string;created_at:number;node_id:string|null;job_id:string|null};
export type State={user:User;jobs:Job[];nodes:Node[];events:Event[];users:User[];server_time:number;version:number;limits:{max_file_mb:number;max_batch_files:number}};
export type Action=(operation:()=>Promise<void>,message?:string)=>Promise<void>;
export const STATUS:Record<Status,string>={queued:'排隊中',loading:'準備中',running:'執行中',retrying:'接力重試',completed:'已完成',failed:'失敗',cancelled:'已取消'};
export const KIND:Record<Kind,string>={asr:'語音轉文字',upscale:'圖片 AI 放大'};
export const active=(s:Status)=>['loading','running'].includes(s);
export const pending=(s:Status)=>['queued','retrying'].includes(s);
export const duration=(s:number)=>s<60?`${Math.max(0,Math.round(s))} 秒`:s<3600?`${(s/60).toFixed(1)} 分`:`${(s/3600).toFixed(1)} 小時`;
export const date=(t:number)=>new Date(t*1000).toLocaleString('zh-TW',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false});
export const bytes=(n:number)=>n<1024*1024?`${(n/1024).toFixed(0)} KB`:`${(n/1024/1024).toFixed(1)} MB`;
export function nodeStatus(n:Node){return n.revoked?'已撤銷':!n.online?'離線':!n.sharing?'未分享':!n.local_enabled?'本機已停止':!n.within_schedule?'時段外':n.current_job?'工作中':Object.keys(n.capabilities).length?'可接單':'環境待準備'}

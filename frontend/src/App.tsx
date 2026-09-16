import { useState,useEffect,useCallback } from 'react';
import { Cpu,ArrowRight,AudioLines,ScanLine,ShieldCheck,LayoutDashboard,Layers,Monitor,Presentation,Settings,LogOut,Menu,X,CheckCircle2,AlertCircle,RefreshCw } from 'lucide-react';
import { api } from './api';
import { type State,type Action } from './types';
import { Workbench } from './Workbench';
import { Jobs } from './Jobs';
import { Nodes } from './Nodes';
import { Admin } from './Admin';
import { Display } from './Display';
import { Modal } from './ui';
import { useWebMCP } from './webmcp';
type Page='workbench'|'jobs'|'nodes'|'display'|'admin';
const pages=[{id:'workbench',label:'任務工作台',icon:LayoutDashboard},{id:'jobs',label:'我的工作',icon:Layers},{id:'nodes',label:'共享設備',icon:Monitor},{id:'display',label:'展示總覽',icon:Presentation},{id:'admin',label:'平台管理',icon:Settings}] as const;
export default function App(){
 const [state,setState]=useState<State|null>(null);const [loading,setLoading]=useState(true);const [online,setOnline]=useState(true);const [initialError,setInitialError]=useState('');
 const [mobile,setMobile]=useState(()=>window.matchMedia('(max-width:720px)').matches);useEffect(()=>{const q=window.matchMedia('(max-width:720px)');const update=()=>setMobile(q.matches);q.addEventListener('change',update);return()=>q.removeEventListener('change',update)},[]);
 const [page,setPage]=useState<Page>('workbench');const [menu,setMenu]=useState(false);const [toast,setToast]=useState<{text:string;error:boolean}|null>(null);const [passwordDialog,setPasswordDialog]=useState(false);
 const refresh=useCallback(async()=>{const next=await api<State>('/state');setState(next);setOnline(true)},[]);
 useEffect(()=>{refresh().catch(e=>{if(e.status!==401)setInitialError(e.message)}).finally(()=>setLoading(false))},[refresh]);
 useEffect(()=>{if(!state?.user.id)return;const events=new EventSource('/api/events');events.addEventListener('state',e=>{setState(JSON.parse((e as MessageEvent).data));setOnline(true)});events.addEventListener('expired',()=>{setState(null);events.close()});events.onerror=()=>setOnline(false);return()=>events.close()},[state?.user.id]);
 useEffect(()=>{if(!toast)return;const t=setTimeout(()=>setToast(null),6000);return()=>clearTimeout(t)},[toast]);
 const action:Action=async(fn,message)=>{try{await fn();await refresh();if(message)setToast({text:message,error:false})}catch(e){setToast({text:(e as Error).message,error:true})}};
 useWebMCP(state,refresh,setPage);
 if(loading)return <div className="boot"><Cpu size={38}/><h2>算力接力站</h2><p>正在連接工作台…</p></div>;
 if(!state)return <Login onLogin={async()=>{await refresh();setInitialError('')}} initialError={initialError}/>;
 const currentPage=pages.find(p=>p.id===page)!;
 return <div className={'app-shell '+(page==='display'?'presentation-shell':'')}>
  {menu&&<button className="nav-backdrop" onClick={()=>setMenu(false)} aria-label="關閉選單"/>}
  <aside className={'sidebar '+(menu?'open':'')} inert={mobile&&!menu}><a className="brand" href="#" onClick={e=>{e.preventDefault();setPage('workbench')}}><Cpu/><span>算力接力站<small>COMPUTE RELAY</small></span></a><div className="workspace-label">校園共享工作空間</div><nav>{pages.filter(p=>p.id!=='admin'||state.user.role==='admin').map(p=><button key={p.id} className={page===p.id?'selected':''} onClick={()=>{setPage(p.id);setMenu(false)}}><p.icon size={19}/>{p.label}{p.id==='jobs'&&<small>{state.jobs.filter(j=>['queued','retrying','loading','running'].includes(j.status)).length}</small>}</button>)}</nav><div className="sidebar-bottom"><div className="network-note"><ShieldCheck size={19}/><div>你的電腦，由你決定<small>需要時隨時停止共享</small></div></div><button className="user-button" onClick={()=>setPasswordDialog(true)}><span className="avatar">{state.user.display_name.slice(0,1)}</span><span>{state.user.display_name}<small>{state.user.role==='admin'?'平台管理者':'校內使用者'}</small></span><Settings size={16}/></button><button className="logout" onClick={async()=>{await api('/auth/logout','POST');setState(null)}}><LogOut size={15}/>登出</button></div></aside>
  <div className="app-main"><header className="topbar"><div className="breadcrumb"><button className="icon-button mobile-menu" onClick={()=>setMenu(!menu)} aria-label="開啟選單"><Menu size={21}/></button><span>工作空間</span><span className="divider">/</span><strong>{currentPage.label}</strong></div><div className="topbar-right"><span className={'connection '+(!online?'lost':'')}><i/>{online?'即時連線中':'連線中斷，重新連線中'}</span><span className="campus-tag">SCU · 校園試用</span></div></header>
  {!online&&<div className="offline-banner"><AlertCircle size={18}/>目前顯示最後一次收到的狀態；恢復連線後會自動更新。<button onClick={()=>action(refresh)}>重試</button></div>}
  <main className="content" id="main-content">{page==='workbench'&&<Workbench state={state} action={action} onJobs={()=>setPage('jobs')}/>}{page==='jobs'&&<Jobs state={state} action={action} onNew={()=>setPage('workbench')}/>}{page==='nodes'&&<Nodes state={state} action={action}/>}{page==='admin'&&state.user.role==='admin'&&<Admin state={state} action={action}/>}{page==='display'&&<Display state={state}/>}</main><footer className="app-footer"><span>算力接力站</span><span>每一次接力，都留下可追蹤的紀錄。</span><span>v0.1 · 校內試用版</span></footer></div>
  {toast&&<div role="status" className={'toast '+(toast.error?'error':'')}>{toast.error?<AlertCircle size={20}/>:<CheckCircle2 size={20}/>}<span>{toast.text}</span><button aria-label="關閉通知" onClick={()=>setToast(null)}><X size={16}/></button></div>}
  {passwordDialog&&<Modal title="變更密碼" onClose={()=>setPasswordDialog(false)}><form onSubmit={async e=>{e.preventDefault();const f=new FormData(e.currentTarget);try{await api('/auth/password','POST',{current_password:f.get('current'),new_password:f.get('new')});setPasswordDialog(false);setState(null);setInitialError('密碼已更新，請重新登入。')}catch(e){setToast({text:(e as Error).message,error:true})}}}><label>目前密碼<input name="current" type="password" required autoComplete="current-password"/></label><label>新密碼（至少 12 個字元）<input name="new" type="password" required minLength={12} autoComplete="new-password"/></label><div className="modal-actions"><button type="button" className="secondary" onClick={()=>setPasswordDialog(false)}>取消</button><button className="primary">更新密碼</button></div></form></Modal>}
 </div>
}
function Login({onLogin,initialError}:{onLogin:()=>Promise<void>;initialError:string}){
 const [username,setUsername]=useState('');const [password,setPassword]=useState('');const [error,setError]=useState(initialError);const [busy,setBusy]=useState(false);
 return <main className="login-shell"><section className="login-story"><div className="brand"><Cpu/><span>算力接力站<small>CAMPUS COMPUTE RELAY</small></span></div><div className="story-main"><span className="eyebrow">讓校園裡的算力，連起來。</span><h1>你的下一個成果，<br/><em>由閒置算力接力。</em></h1><p>提交音訊或圖片，交給開啟共享的 GPU。<br/>在同一個工作台，追蹤每一步與最後的成果。</p><div className="service-pills"><span><AudioLines size={19}/> 語音轉文字</span><span><ScanLine size={19}/> 圖片 AI 放大</span></div></div><div className="story-footer"><ShieldCheck size={17}/> 校內共享 · 機主隨時收回 · 任務自動接力</div></section><section className="login-form-side"><form className="login-form" onSubmit={async e=>{e.preventDefault();setBusy(true);setError('');try{await api('/auth/login','POST',{username,password});await onLogin()}catch(e){setError((e as Error).message)}finally{setBusy(false)}}}><span className="eyebrow">歡迎回來</span><h2>登入工作台</h2><p>使用管理者提供的校內測試帳號。</p><label>帳號<input autoComplete="username" required value={username} onChange={e=>setUsername(e.target.value)} placeholder="輸入帳號"/></label><label>密碼<input type="password" autoComplete="current-password" required value={password} onChange={e=>setPassword(e.target.value)} placeholder="輸入密碼"/></label>{error&&<p role="alert" className="error-box">{error}</p>}<button className="primary" type="submit" disabled={busy}>{busy?'正在登入':'進入工作台'}{busy?<RefreshCw size={18} className="spin"/>:<ArrowRight size={18}/>}</button><p className="form-note">第一次使用？請向管理者索取帳號。<br/>提供 GPU 的電腦另需啟動接力程式。</p></form></section></main>
}


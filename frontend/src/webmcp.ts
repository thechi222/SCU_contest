import { useEffect,useRef } from 'react';
import { type State } from './types';
type Page='workbench'|'jobs'|'nodes'|'display'|'admin';
type ModelContext={registerTool:(tool:{name:string;description:string;inputSchema:object;execute:(args:Record<string,unknown>)=>Promise<unknown>},options:{signal:AbortSignal})=>void};
export function useWebMCP(state:State|null,_refresh:()=>Promise<void>,navigate:(p:Page)=>void){
 const current=useRef(state);current.current=state;
 useEffect(()=>{const model=(navigator as Navigator&{modelContext?:ModelContext}).modelContext;if(!model||!state)return;const control=new AbortController();try{model.registerTool({name:'relay_status',description:'讀取目前登入者可見的算力接力站工作與設備摘要。',inputSchema:{type:'object',properties:{},additionalProperties:false},execute:async()=>({content:[{type:'text',text:JSON.stringify({jobs:current.current?.jobs.map(j=>({id:j.id,name:j.filename,status:j.status})),nodes:current.current?.nodes.map(n=>({name:n.name,online:n.online,sharing:n.sharing}))})}]})},{signal:control.signal});model.registerTool({name:'relay_navigate',description:'開啟算力接力站的操作頁面。',inputSchema:{type:'object',properties:{page:{type:'string',enum:['workbench','jobs','nodes','display']}},required:['page'],additionalProperties:false},execute:async args=>{if(!['workbench','jobs','nodes','display'].includes(String(args.page)))throw Error('無效頁面');navigate(args.page as Page);return {content:[{type:'text',text:'已開啟頁面'}]}}},{signal:control.signal})}catch{/* Optional browser API; the app works without it. */}return()=>control.abort()},[state?.user.id,navigate]);
}

export async function api<T=Record<string,unknown>>(path:string,method='GET',body?:unknown):Promise<T>{
 const res=await fetch('/api'+path,{method,credentials:'same-origin',headers:{'X-Relay-Request':'1',...(body!==undefined?{'Content-Type':'application/json'}:{})},body:body!==undefined?JSON.stringify(body):undefined});
 if(!res.ok){const data=await res.json().catch(()=>({detail:'服務暫時無法連線'}));const error=new Error(typeof data.detail==='string'?data.detail:'輸入資料不正確，請檢查欄位') as Error&{status:number};error.status=res.status;throw error;}
 return res.json();
}
export function upload(form:FormData,onProgress:(p:number)=>void):Promise<{batch_id:string}>{return new Promise((resolve,reject)=>{const xhr=new XMLHttpRequest();xhr.open('POST','/api/batches');xhr.setRequestHeader('X-Relay-Request','1');xhr.upload.onprogress=e=>{if(e.lengthComputable)onProgress(e.loaded/e.total)};xhr.onload=()=>{let data;try{data=JSON.parse(xhr.responseText)}catch{reject(Error('服務回應異常'));return}if(xhr.status>=200&&xhr.status<300)resolve(data);else reject(Error(typeof data.detail==='string'?data.detail:'上傳資料不正確'))};xhr.onerror=()=>reject(Error('上傳中斷，請檢查網路'));xhr.send(form)})}

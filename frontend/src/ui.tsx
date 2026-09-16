import { useEffect,useRef,type ReactNode } from 'react';
import { X,Inbox,LoaderCircle } from 'lucide-react';
import { type Status,STATUS } from './types';
export function Badge({status}:{status:Status}){return <span className={'badge '+status}>{['running','loading'].includes(status)&&<LoaderCircle size={13} className="spin"/>}{STATUS[status]}</span>}
export function Empty({title,description,children}:{title:string;description:string;children?:ReactNode}){return <div className="empty"><div className="empty-icon"><Inbox size={27}/></div><h3>{title}</h3><p>{description}</p>{children}</div>}
export function Modal({title,onClose,children,wide=false}:{title:string;onClose:()=>void;children:ReactNode;wide?:boolean}){
 const ref=useRef<HTMLDialogElement>(null);useEffect(()=>{const d=ref.current;d?.showModal();return()=>d?.close()},[]);
 return <dialog ref={ref} className={'modal '+(wide?'wide':'')} onCancel={onClose} onClick={e=>{if(e.target===ref.current)onClose()}} aria-label={title}><div className="modal-heading"><h2>{title}</h2><button className="icon-button" onClick={onClose} aria-label="關閉"><X size={21}/></button></div>{children}</dialog>
}
export function Stat({label,value,detail,accent=false}:{label:string;value:string|number;detail:string;accent?:boolean}){return <div className={'stat '+(accent?'accent':'')}><span>{label}</span><strong>{value}</strong><small>{detail}</small></div>}

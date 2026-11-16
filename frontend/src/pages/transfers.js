import {jobs,transfers} from '../api/entities.js';
import {workspace} from '../stores/workspace.js';
import {session} from '../stores/session.js';
import {heading} from '../components/common/shell.js';
import {table} from '../components/common/table.js';
import {esc,date,notify} from '../utils/dom.js';
import {submit} from '../hooks/forms.js';
import {TransferStatus} from '../constants/enums.js';
const stationNames=()=>((workspace.meta.parameters||[]).find(p=>p.key==='station')?.options||[]).map(o=>o.value).filter(v=>v!=='全部');
const writable=()=>session.user.role!=='viewer';
function statusBadge(s){return '<span class="status transfer-'+esc(s)+'">'+esc(TransferStatus[s]||s)+'</span>';}
function statusSummary(list){
 const order=['draft','reserved','partial','settled','cancelled'];
 return order.map(s=>TransferStatus[s]+' '+list.filter(t=>t.status===s).length).join(' · ');
}
function transferCard(t){
 const done=['settled','cancelled'].includes(t.status),active=['reserved','partial'].includes(t.status);
 const nextKey='T'+t.id+'-'+(t.batches.length+1);
 return '<article class="transfer-card"><div class="transfer-head"><div><strong>#'+t.id+' '+esc(t.origin)+' → '+esc(t.destination)+'</strong>'+statusBadge(t.status)+'</div><span>计划 '+t.quantity+' 辆 · 实搬 '+t.moved_quantity+' · 释放 '+t.released_quantity+' · 未搬 '+t.remaining+'</span></div>'+
  '<small>引用研究 #'+t.job_id+' · 草稿 '+date(t.created_at)+(t.confirmed_at?' · 预占 '+date(t.confirmed_at):'')+'</small>'+
  (t.batches.length?'<ul class="batch-log">'+t.batches.map(b=>'<li>批次 '+esc(b.batch_key)+' · '+b.quantity+' 辆 · '+date(b.created_at)+'</li>').join('')+'</ul>':'')+
  (!done&&writable()?'<div class="transfer-actions">'+(t.status==='draft'?'<button class="small primary" data-confirm="'+t.id+'">确认预占 '+t.quantity+' 辆</button>':'<form class="batch-form" data-batch="'+t.id+'"><label>批次号<input name="batch_key" value="'+esc(nextKey)+'" required maxlength="120"></label><label>实搬车数<input name="quantity" type="number" min="1" max="'+t.remaining+'" value="'+t.remaining+'" required></label><button class="small" type="submit">回报本批</button></form>')+'<button class="small" data-cancel="'+t.id+'">'+(t.status==='draft'?'撤销草稿':'取消未搬部分')+'</button></div>':'')+
  '</article>';
}
export async function transferPage(){
 const [allJobs,stations,list]=await Promise.all([jobs.list(),transfers.stations(),transfers.list()]);workspace.transfers=list;workspace.stations=stations;
 const approved=allJobs.filter(j=>j.approved&&j.status==='completed');
 const known={};stations.forEach(s=>known[s.name]=s);
 const names=stationNames();
 const options=names.map(n=>'<option value="'+esc(n)+'">'+esc(n)+'</option>').join('');
 const initFields=names.map(n=>'<label>'+esc(n)+' 初始车数<input type="number" min="0" name="initial-'+esc(n)+'" '+(known[n]?'value="'+known[n].initial_bikes+'"':'placeholder="未登记"')+'><small class="hint">'+(known[n]?'已登记；台账有变动后锁定':'填写后建账')+'</small></label>').join('');
 const stationColumns=[{key:'name',label:'站点'},{key:'initial_bikes',label:'初始车数'},{key:'moved_in',label:'累计调入'},{key:'moved_out',label:'累计调出'},{key:'actual',label:'实有车'},{key:'reserved',label:'已预占'},{key:'available',label:'可用车'}];
 return heading('06 / TRANSFER DESK','跨站调拨台账','把已批准的研究结论落到补车动作：录入各站初始车数，确认时预占余车，按批回报实搬。并发确认不超卖，同批重试只记一次。','<button class="button" id="refresh-transfers">刷新台账 ↻</button>')+
  '<div class="transfer-grid"><section class="panel"><div class="section-title"><h2>新建调拨草稿</h2><span>'+(approved.length?approved.length+' 份已批准研究':'暂无已批准研究')+'</span></div>'+
  (approved.length?'<form id="transfer-form"><label>引用已批准研究<select name="job_id">'+approved.map(j=>'<option value="'+j.id+'">'+esc(j.name)+'</option>').join('')+'</select></label><div class="parameter-grid"><label>调出站<select name="origin">'+options+'</select></label><label>调入站<select name="destination">'+options+'</select></label></div><label>调拨车数<input name="quantity" type="number" min="1" value="10" required></label><div class="section-title"><h2>站点初始车数</h2><span>至少填写调出站与调入站</span></div><div class="parameter-grid">'+initFields+'</div><button type="submit" class="primary" '+(writable()?'':'disabled')+'>保存调拨草稿</button><p class="hint">草稿只记录计划，不占车。确认预占时才校验调出站可用车；同一研究可拆成多张调拨单。尚未发生车辆变动的站点仍可修正初始车数。</p></form>':'<div class="empty">先到结果复核页批准一份已完成研究，再创建调拨单。</div>')+
  '</section><section class="panel"><div class="section-title"><h2>站点车辆台账</h2><span>可用 = 实有 − 已预占</span></div>'+table(stationColumns,stations,'尚无站点台账。创建首张调拨单时录入初始车数。')+
  '<div class="section-title" style="margin-top:32px"><h2>未结与历史调拨</h2><span>'+statusSummary(list)+'</span></div><div class="transfer-list">'+(list.length?list.map(transferCard).join(''):'<div class="empty">还没有调拨单。批准研究后可在此安排补车。</div>')+'</div></section></div>';
}
export function bindTransfers(refresh){
 document.querySelector('#refresh-transfers').onclick=refresh;
 const form=document.querySelector('#transfer-form');
 if(form)submit(form,async f=>{
  const stations=[];stationNames().forEach(n=>{
   let v=f.get('initial-'+n);
   if(v===null||v===''){const known=workspace.stations.find(s=>s.name===n);v=known?String(known.initial_bikes):'';}
   if(v!=='')stations.push({name:n,initial_bikes:Number(v)});
  });
  await transfers.create({job_id:Number(f.get('job_id')),origin:f.get('origin'),destination:f.get('destination'),quantity:Number(f.get('quantity')),stations});
  notify('调拨草稿已保存，确认后才会预占余车');await refresh();
 });
 document.querySelectorAll('[data-confirm]').forEach(b=>b.onclick=async()=>{try{await transfers.confirm(b.dataset.confirm);notify('余车已预占，可以开始分批实搬');await refresh();}catch(e){notify(e.message,true);}});
 document.querySelectorAll('[data-cancel]').forEach(b=>b.onclick=async()=>{const text=b.textContent.includes('撤销')?'撤销草稿后不能再次确认预占。继续？':'取消后将释放未搬部分的预占，已搬车辆不回滚。继续？';if(!confirm(text))return;try{await transfers.cancel(b.dataset.cancel);notify(b.textContent.includes('撤销')?'草稿已撤销':'未搬部分已取消并释放预占');await refresh();}catch(e){notify(e.message,true);}});
 document.querySelectorAll('[data-batch]').forEach(f=>submit(f,async d=>{let r;try{r=await transfers.batch(f.dataset.batch,{batch_key:d.get('batch_key'),quantity:Number(d.get('quantity'))});}catch(e){notify(e.message,true);await refresh();return;}notify(r.replayed?'同批回报已记账，本次重试不重复扣减':'本批实搬已记账，调出与调入同时更新');await refresh();}));
}

const seatState={busy:false,follow:true};const feedback=document.querySelector('#feedback');const form=document.querySelector('#events');form?.addEventListener('submit',async e=>{e.preventDefault();if(seatState.busy)return;seatState.busy=true;const b=form.querySelector('button');b.disabled=true;b.textContent='REPLAYING';try{const params={observation_end:form.elements.observation_end.value,late_minutes:form.elements.late_minutes.value};let options;if(form.elements.file.files[0]){const body=new FormData();body.append('file',form.elements.file.files[0]);body.append('params',JSON.stringify(params));options={method:'POST',body};}else options={method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:form.elements.text.value,params})};const res=await fetch('/api/runs',options);const result=await res.json();if(!res.ok)throw Error(result.message);location.assign('/m/5?run='+result.manifest.run_id);}catch(err){feedback.textContent=err.message;}finally{seatState.busy=false;b.disabled=false;b.textContent='RUN / 回放';}});const review=document.querySelector('#review');review?.addEventListener('submit',async e=>{e.preventDefault();try{const res=await fetch('/api/review/'+review.dataset.run,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({version:Number(review.dataset.version),decision:review.elements.decision.value})});const result=await res.json();if(!res.ok)throw Error(result.message);location.reload();}catch(err){feedback.textContent=err.message;}});const tail=document.querySelector('.log-tail');document.querySelector('#pause')?.addEventListener('click',e=>{seatState.follow=!seatState.follow;e.target.textContent=seatState.follow?'暂停滚动':'跟随日志';if(tail&&seatState.follow)tail.scrollTop=0;});

const knownRuns=new Set();
async function appendRunEvents(){
 if(!tail)return;
 try{
  const res=await fetch('/api/history');if(!res.ok)throw Error('运行清单暂不可用');
  const runs=await res.json();
  for(const run of [...runs].reverse()){
   const key=run.id+':'+run.version;
   if(knownRuns.has(key))continue;knownRuns.add(key);
   const line=document.createElement('div');
   const stamp=document.createElement('time');stamp.textContent=new Date().toISOString().slice(11,19);
   const label=document.createElement('b');label.textContent='BATCH';
   const ident=document.createElement('code');ident.textContent=run.id.slice(0,12);
   const detail=document.createElement('span');detail.textContent=run.review+' / V'+run.version;
   line.append(stamp,label,ident,detail);tail.prepend(line);
   if(seatState.follow)tail.scrollTop=0;
  }
 }catch(err){feedback.textContent=err.message;}
 finally{setTimeout(appendRunEvents,5000);}
}
appendRunEvents();

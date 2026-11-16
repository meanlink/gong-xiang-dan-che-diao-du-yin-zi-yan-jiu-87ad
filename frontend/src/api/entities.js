import {api} from './client.js';
export const datasets={list:()=>api('/datasets'),get:id=>api('/datasets/'+id),create:data=>api('/datasets',{method:'POST',body:JSON.stringify(data)})};
export const jobs={list:()=>api('/jobs'),get:id=>api('/jobs/'+id),create:data=>api('/jobs',{method:'POST',body:JSON.stringify(data)}),approve:id=>api('/jobs/'+id+'/approve',{method:'POST'})};
export const reports={list:()=>api('/reports'),create:data=>api('/reports',{method:'POST',body:JSON.stringify(data)}),toggle:id=>api('/reports/'+id+'/toggle',{method:'POST'}),deliveries:()=>api('/deliveries')};
export const transfers={list:()=>api('/transfers'),get:id=>api('/transfers/'+id),stations:()=>api('/stations'),create:data=>api('/transfers',{method:'POST',body:JSON.stringify(data)}),confirm:id=>api('/transfers/'+id+'/confirm',{method:'POST'}),batch:(id,data)=>api('/transfers/'+id+'/batches',{method:'POST',body:JSON.stringify(data)}),cancel:id=>api('/transfers/'+id+'/cancel',{method:'POST'})};

/** @typedef {{id:number,name:string,source:string,rows:number,checksum:string}} Dataset */
/** @typedef {{id:number,name:string,dataset_id:number,status:string,result:Object,approved:boolean}} AnalysisJob */
/** @typedef {{id:number,name:string,job_id:number,destination:string,next_run:number,enabled:boolean}} ReportSchedule */
/** @typedef {{id:number,name:string,initial_bikes:number,moved_in:number,moved_out:number,reserved:number,actual:number,available:number}} StationLedger */
/** @typedef {{id:number,batch_key:string,quantity:number,created_at:number}} TransferBatch */
/** @typedef {{id:number,job_id:number,origin:string,destination:string,quantity:number,moved_quantity:number,released_quantity:number,remaining:number,status:string,confirmed_at:number|null,settled_at:number|null,batches:TransferBatch[]}} TransferOrder */
export {};


async function apiFetch(url, opt={}){
  const r = await fetch(url, Object.assign({credentials:'same-origin'}, opt));
  if(r.status === 401){ location.href='/login'; throw new Error('401'); }
  const ct = r.headers.get('content-type') || '';
  return ct.includes('application/json') ? r.json() : r.text();
}
const apiGet  = (u) => apiFetch(u);
const apiPost = (u, bodyObj) => apiFetch(u, { method:'POST', headers:{'Content-Type':'application/x-www-form-urlencoded'}, body:new URLSearchParams(bodyObj||{}) });
function mountSSE(url, onmsg){
  const es = new EventSource(url, {withCredentials:true});
  es.onmessage = (e)=> onmsg(JSON.parse(e.data));
  es.onerror = ()=> es.close();
  return es;
}

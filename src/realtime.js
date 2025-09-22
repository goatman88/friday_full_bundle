export function connectRealtime(){
  const ws = new WebSocket((location.protocol==='https:'?'wss':'ws') + '://' + location.host + '/ws/realtime');
  ws.onopen = ()=> console.log('WS open')
  ws.onmessage = (e)=> console.log('WS', e.data)
  ws.onerror = (e)=> console.error('WS error', e)
  ws.onclose = ()=> console.log('WS closed')
  return ws
}

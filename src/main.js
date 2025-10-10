fetch(`${__BACKEND__}/api/health`).then(r=>r.json()).then(console.log)

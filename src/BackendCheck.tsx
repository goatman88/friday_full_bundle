import { useState } from "react";
import { pingBoth } from "./api";

export default function BackendCheck() {
  const [result, setResult] = useState("(click to test)");

  async function test() {
    try {
      const data = await pingBoth();
      setResult(JSON.stringify(data));
    } catch (e: any) {
      setResult(`Error: ${e.message || e}`);
    }
  }

  return (
    <div style={{padding:"12px", border:"1px solid #ddd", borderRadius:6}}>
      <button onClick={test}>Test backend /health + /api/health</button>
      <pre>{result}</pre>
    </div>
  );
}

import { Sparkles } from "lucide-react";
import { useState, type FormEvent } from "react";
import { post } from "../lib/api";
import { PageIntro } from "../components/AsyncPanel";

export function MagicDudePage() {
  const [question, setQuestion] = useState("");
  const [message, setMessage] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault();
    const result = await post<Record<string, unknown>>("/v1/owner/magic-dude/explain", { question });
    setMessage(result.status === "coming_soon" ? "Coming soon — Magic Dude is not connected yet." : String(result.explanation ?? "No explanation available."));
  }
  return <><PageIntro title="Magic Dude" description="A read-and-explain advisor for your shop. It cannot change a router; recommendations become Safe Change proposals for owner review." /><section className="panel form-panel"><p className="kicker"><Sparkles size={16} /> Ask about your shop</p><form onSubmit={submit}><label>Question<textarea value={question} onChange={(event) => setQuestion(event.target.value)} required /></label><button className="primary">Explain</button></form>{message && <p className="notice">{message}</p>}</section></>;
}

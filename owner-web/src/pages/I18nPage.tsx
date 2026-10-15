import { Languages } from "lucide-react";
import { useState } from "react";
import { PageIntro } from "../components/AsyncPanel";

export function I18nPage() {
  const [language, setLanguage] = useState(() => localStorage.getItem("mm.owner.language") || "en");
  function choose(next: string) { setLanguage(next); localStorage.setItem("mm.owner.language", next); document.documentElement.lang = next; document.documentElement.dataset.lang = next; }
  return <><PageIntro kicker="Language" title="Choose your language" description="Pick the language that is most comfortable for your daily shop work." /><section className="language-grid"><button className={language === "my" ? "selected" : ""} onClick={() => choose("my")}><Languages /><strong>မြန်မာ</strong><span>Burmese</span></button><button className={language === "en" ? "selected" : ""} onClick={() => choose("en")}><Languages /><strong>English</strong><span>English</span></button></section><p className="muted">Some product and RouterOS terms may still appear in English while translation coverage grows.</p></>;
}

import { BookOpen, Router, ShieldCheck, Ticket, Wifi } from "lucide-react";
import { PageIntro } from "../components/AsyncPanel";

export function ManualPage() {
  return <><PageIntro kicker="Help" title="MikroMagic manual" description="Short, practical steps for the jobs you do most often." />
    <section className="manual-grid"><Guide icon={Router} title="Connect a router" steps={["Add the router with a shop name.", "Choose Connect with Magic Hub.", "Paste the generated script once in WinBox Terminal.", "Wait for Connected before managing the hotspot."]} /><Guide icon={Ticket} title="Prepare vouchers" steps={["Choose the package and quantity.", "Review the print layout.", "Generate codes only when you are ready to print.", "Record whether every sheet printed correctly."]} /><Guide icon={Wifi} title="Update the guest page" steps={["Edit the shop welcome and help details.", "Save the page in MikroMagic.", "Publish when the preview looks right.", "Use Safe Change separately when installing it on a router."]} /><Guide icon={ShieldCheck} title="Use Safe Change" steps={["Open a connected router.", "Prepare a preview from the latest live state.", "Review the exact difference and risk.", "Confirm only when you are ready; MikroMagic keeps backup and rollback checks in place."]} /></section>
  </>;
}

function Guide({ icon: Icon, title, steps }: { icon: typeof Router; title: string; steps: string[] }) {
  return <article className="panel guide"><span className="card-icon"><Icon /></span><h2>{title}</h2><ol>{steps.map((step) => <li key={step}>{step}</li>)}</ol></article>;
}

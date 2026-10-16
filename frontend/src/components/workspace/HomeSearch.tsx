import { AceLogo, AceWordmark } from "./AceLogo"
import { GraphSearch } from "./GraphSearch"

type Props = {
  busy: boolean
  error: string
  onSubmit: (value: string) => void
}

const channels = ["Name search", "Domain and URL", "Registration records", "Certificates"]

export function HomeSearch({ busy, error, onSubmit }: Props) {
  return (
    <div className="relative flex min-h-0 flex-1 overflow-y-auto bg-[#eef1f4]">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          backgroundImage:
            "linear-gradient(to right, rgba(15,23,42,0.045) 1px, transparent 1px), linear-gradient(to bottom, rgba(15,23,42,0.045) 1px, transparent 1px)",
          backgroundSize: "56px 56px",
          maskImage: "radial-gradient(ellipse at 50% 45%, black 20%, transparent 76%)",
          WebkitMaskImage: "radial-gradient(ellipse at 50% 45%, black 20%, transparent 76%)",
        }}
      />
      <div className="relative mx-auto flex w-full max-w-[1040px] items-center px-5 py-6 sm:px-6">
        <div className="grid w-full items-center gap-6 md:grid-cols-[210px_minmax(0,1fr)] md:gap-8">
          <aside className="flex items-start gap-3.5 md:block">
            <AceLogo size={44} className="shrink-0" />
            <div>
              <div className="md:mt-4">
                <AceWordmark className="text-[22px] md:text-[24px]" />
              </div>
              <p className="mt-1 text-[10px] font-medium uppercase tracking-[0.18em] text-slate-500">Open-source intelligence</p>
              <p className="mt-3 hidden max-w-[200px] text-[12.5px] leading-relaxed text-slate-600 md:block">
                A desk for public-record investigations. Each search opens its own case.
              </p>
              <ul className="mt-5 hidden space-y-1.5 md:block">
                {channels.map((channel, index) => (
                  <li key={channel} className="flex items-center gap-2 text-[12px] text-slate-600">
                    <span className="w-4 font-mono text-[10px] text-slate-400">0{index + 1}</span>
                    <span className="h-px w-2.5 bg-slate-300" />
                    {channel}
                  </li>
                ))}
              </ul>
            </div>
          </aside>

          <section className="rounded-xl border border-slate-200 bg-white px-5 py-5 shadow-[0_24px_60px_-36px_rgba(15,23,42,0.55)] sm:px-6 sm:py-6">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] font-medium uppercase tracking-[0.16em] text-slate-400">
              <span>New case</span>
              <span className="hidden h-3 w-px bg-slate-200 sm:block" />
              <span className="inline-flex items-center gap-1.5 text-teal-800">
                <span className="h-1.5 w-1.5 rounded-full bg-teal-600" />
                Public collection
              </span>
            </div>
            <h1 className="mt-2.5 text-[26px] font-semibold tracking-tight text-slate-950">Start an investigation</h1>
            <p className="mt-1.5 max-w-lg text-[13.5px] leading-relaxed text-slate-600">
              Search a full name or a website. Each query opens its own results.
            </p>
            <div className={busy || error ? "mt-5 mb-8" : "mt-5"}>
              <GraphSearch value="" busy={busy} error={error} onSubmit={onSubmit} size="hero" />
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}

import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Accessibility — LegiLens",
  description:
    "LegiLens accessibility statement, WCAG 2.1 Level AA conformance target, testing methodology, and contact path for accessibility issues.",
};

export default function Accessibility() {
  return (
    <main id="main" className="mx-auto max-w-3xl px-4 py-12 space-y-10 text-slate-200">
      <header>
        <h1 className="text-4xl font-black tracking-tight text-white">Accessibility</h1>
        <p className="mt-3 text-slate-400">
          LegiLens is a public transparency tool. We believe everyone — including
          users of screen readers, keyboard-only navigators, and assistive
          technology — has the right to access public legislative information.
        </p>
      </header>

      <section className="space-y-3">
        <h2 className="text-2xl font-bold text-white">Conformance target</h2>
        <p>
          LegiLens targets <strong>WCAG 2.1 Level AA</strong> conformance across all
          public pages. The codebase is tested automatically and manually
          against this standard.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-2xl font-bold text-white">Testing methodology</h2>
        <p>Every pull request that touches the frontend is verified through:</p>
        <ul className="list-disc pl-6 space-y-1">
          <li>jest-axe automated scans on every component test (CI-blocking)</li>
          <li>@axe-core/playwright scans after every end-to-end navigation (CI-blocking)</li>
          <li>Manual keyboard-only walkthrough per route</li>
          <li>Manual screen reader walkthrough (VoiceOver on macOS)</li>
          <li>Color contrast verification on each text/background pair</li>
          <li>200% zoom and 320px viewport reflow checks</li>
        </ul>
      </section>

      <section className="space-y-3">
        <h2 className="text-2xl font-bold text-white">Known limitations</h2>
        <p>
          None reported at this time. If you encounter a barrier, please report
          it (see below) — we treat accessibility regressions as bugs.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-2xl font-bold text-white">Reporting accessibility issues</h2>
        <p>
          The fastest path is opening an issue on GitHub:{" "}
          <a
            href="https://github.com/EMSwank/legilens/issues/new?labels=a11y"
            className="text-blue-300 underline"
            target="_blank"
            rel="noopener noreferrer"
          >
            github.com/EMSwank/legilens/issues
          </a>
          .
        </p>
        <p>
          Please include the page URL, your assistive technology and browser
          (if relevant), and a description of the barrier. We aim to acknowledge
          reports within five business days.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-2xl font-bold text-white">Ongoing commitment</h2>
        <p>
          Accessibility work is ongoing. Each new feature is built against this
          standard from the start rather than retrofitted. If a regression
          slips through, we treat fixing it the same priority as fixing a
          functional bug.
        </p>
      </section>
    </main>
  );
}

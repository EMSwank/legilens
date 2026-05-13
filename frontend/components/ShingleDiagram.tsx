export default function ShingleDiagram() {
  return (
    <figure className="my-6">
      <svg
        role="img"
        aria-labelledby="shingle-title shingle-desc"
        viewBox="0 0 600 180"
        className="w-full max-w-xl"
      >
        <title id="shingle-title">3-shingling of a sentence</title>
        <desc id="shingle-desc">
          A sentence broken into overlapping three-word windows, each forming
          one shingle in the MinHash sketch.
        </desc>

        {/* Original sentence */}
        <text x="20" y="30" className="fill-slate-200" fontSize="14" fontFamily="ui-monospace, monospace">
          the quick brown fox jumps over
        </text>

        {/* Shingle 1: "the quick brown" */}
        <rect x="14" y="50" width="155" height="22" fill="rgb(59 130 246 / 0.2)" stroke="rgb(59 130 246)" />
        <text x="20" y="66" className="fill-blue-200" fontSize="12" fontFamily="ui-monospace, monospace">
          the quick brown
        </text>

        {/* Shingle 2: "quick brown fox" */}
        <rect x="44" y="80" width="160" height="22" fill="rgb(59 130 246 / 0.2)" stroke="rgb(59 130 246)" />
        <text x="50" y="96" className="fill-blue-200" fontSize="12" fontFamily="ui-monospace, monospace">
          quick brown fox
        </text>

        {/* Shingle 3: "brown fox jumps" */}
        <rect x="88" y="110" width="160" height="22" fill="rgb(59 130 246 / 0.2)" stroke="rgb(59 130 246)" />
        <text x="94" y="126" className="fill-blue-200" fontSize="12" fontFamily="ui-monospace, monospace">
          brown fox jumps
        </text>

        {/* Shingle 4: "fox jumps over" */}
        <rect x="130" y="140" width="150" height="22" fill="rgb(59 130 246 / 0.2)" stroke="rgb(59 130 246)" />
        <text x="136" y="156" className="fill-blue-200" fontSize="12" fontFamily="ui-monospace, monospace">
          fox jumps over
        </text>
      </svg>
      <figcaption className="mt-2 text-sm text-slate-400">
        Each three-word window forms one shingle. The full set of shingles
        becomes the document signature.
      </figcaption>
    </figure>
  );
}

"use client";
import { RadialBarChart, RadialBar, PolarAngleAxis } from "recharts";

interface Props {
  score: number;
  copycatAlert: boolean;
}

export default function ISTScoreGauge({ score, copycatAlert }: Props) {
  const color = copycatAlert ? "#EF4444" : score < 60 ? "#F59E0B" : "#22C55E";
  const data = [{ value: score, fill: color }];
  const label = `Source Authenticity Score: ${score.toFixed(2)} out of 100.${copycatAlert ? " Copycat alert triggered." : ""}`;

  return (
    <div
      className="flex flex-col items-center gap-2"
      role="img"
      aria-label={label}
    >
      <RadialBarChart
        width={180}
        height={180}
        innerRadius={60}
        outerRadius={85}
        data={data}
        startAngle={180}
        endAngle={0}
      >
        <PolarAngleAxis type="number" domain={[0, 100]} angleAxisId={0} tick={false} />
        <RadialBar dataKey="value" angleAxisId={0} background={{ fill: "#1e293b" }} />
      </RadialBarChart>
      <div className="text-center -mt-12" aria-hidden="true">
        <p className="text-3xl font-black" style={{ color }}>
          {score.toFixed(2)}
        </p>
        <p className="text-xs text-slate-400">Source Authenticity Score</p>
        {copycatAlert && (
          <span className="mt-1 inline-block rounded-full bg-red-500/20 px-2 py-0.5 text-xs font-semibold text-red-400 ring-1 ring-red-500/40">
            COPYCAT ALERT
          </span>
        )}
      </div>
    </div>
  );
}

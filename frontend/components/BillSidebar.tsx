import type { ISTScore, FrictionTag } from "@/lib/types";
import ISTScoreGauge from "./ISTScoreGauge";
import PendingBanner from "./PendingBanner";
import TagBadge from "./TagBadge";

interface Props {
  istScore: ISTScore | null;
  tags: FrictionTag[];
}

export default function BillSidebar({ istScore, tags }: Props) {
  return (
    <div className="space-y-4">
      {istScore ? (
        <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-4">
          <ISTScoreGauge
            score={istScore.source_authenticity_score}
            copycatAlert={istScore.copycat_alert}
          />
        </div>
      ) : (
        <PendingBanner />
      )}
      {tags.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {tags.map((tag) => (
            <TagBadge key={tag.tag_type} type={tag.tag_type} />
          ))}
        </div>
      )}
    </div>
  );
}

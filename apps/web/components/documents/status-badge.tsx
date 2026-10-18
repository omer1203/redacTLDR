import { Badge } from "@/components/ui/badge";
import { statusMeta } from "@/lib/status";
import { cn } from "@/lib/utils";

export function StatusBadge({ status, stage }: { status: string; stage?: string | null }) {
  const meta = statusMeta(status, stage);
  const Icon = meta.icon;
  return (
    <Badge className={cn("gap-1", meta.badgeClass)}>
      <Icon className={cn("h-3 w-3", meta.inProgress && status !== "CREATED" && status !== "UPLOADED" && "animate-spin")} />
      {meta.label}
    </Badge>
  );
}

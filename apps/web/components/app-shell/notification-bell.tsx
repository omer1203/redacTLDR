"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { listNotifications, markNotificationsRead } from "@/lib/api/notifications";
import { formatUtc } from "@/lib/format";
import { useApiToken } from "@/lib/review/token";

export function NotificationBell() {
  const getToken = useApiToken();
  const queryClient = useQueryClient();
  const seen = useRef<Set<string>>(new Set());
  const primed = useRef(false);
  const query = useQuery({
    queryKey: ["notifications"],
    queryFn: async () => listNotifications(await getToken()),
    refetchInterval: 8000,
  });
  const mark = useMutation({
    mutationFn: async (ids: string[] | "all") => markNotificationsRead(await getToken(), ids),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });

  useEffect(() => {
    const rows = query.data ?? [];
    if (!primed.current) {
      rows.forEach((row) => seen.current.add(row.id));
      primed.current = query.isSuccess;
      return;
    }
    for (const row of rows) {
      if (seen.current.has(row.id) || row.readAt) {
        continue;
      }
      seen.current.add(row.id);
      toast.message(row.title);
    }
  }, [query.data, query.isSuccess]);

  const unread = (query.data ?? []).filter((row) => !row.readAt).length;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" aria-label={unread ? `${unread} unread notices` : "Notices"}>
          <span className="relative">
            <Bell className="h-4 w-4" />
            {unread > 0 ? <span className="absolute -right-1 -top-1 h-2 w-2 rounded-full bg-primary" /> : null}
          </span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-80">
        {(query.data ?? []).length === 0 ? (
          <DropdownMenuItem disabled>No notices yet</DropdownMenuItem>
        ) : (
          query.data?.map((row) => (
            <DropdownMenuItem key={row.id} asChild>
              <Link
                href={row.documentId ? `/documents/${row.documentId}` : "/dashboard"}
                onClick={() => mark.mutate([row.id])}
                className="flex flex-col items-start gap-1"
              >
                <span className={row.readAt ? "text-muted-foreground" : "font-medium"}>{row.title}</span>
                <span className="text-xs text-muted-foreground">{formatUtc(row.createdAt)}</span>
              </Link>
            </DropdownMenuItem>
          ))
        )}
        {unread > 0 ? (
          <DropdownMenuItem onSelect={() => mark.mutate("all")}>Mark all read</DropdownMenuItem>
        ) : null}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

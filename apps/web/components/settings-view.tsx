"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { deleteAccount, getSettings, saveSettings, type AccountSettings } from "@/lib/api/settings";
import { DOCUMENT_MODES } from "@/lib/modes";
import { useApiToken } from "@/lib/review/token";
import type { DocumentMode } from "@/lib/types";

export function SettingsView() {
  const getToken = useApiToken();
  const queryClient = useQueryClient();
  const [confirming, setConfirming] = useState(false);
  const query = useQuery({
    queryKey: ["settings"],
    queryFn: async () => getSettings(await getToken()),
    staleTime: 60_000,
  });
  const save = useMutation({
    mutationFn: async (settings: AccountSettings) => saveSettings(await getToken(), settings),
    onSuccess: async (settings) => {
      queryClient.setQueryData(["settings"], settings);
      toast.success("Settings saved");
    },
    onError: (error: Error) => toast.error(error.message),
  });
  const wipe = useMutation({
    mutationFn: async () => deleteAccount(await getToken()),
    onSuccess: () => {
      setConfirming(false);
      toast.success("Deletion queued. Files and records will be removed.");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const prefs = query.data;
  const update = (patch: Partial<AccountSettings>) => {
    if (!prefs) {
      return;
    }
    queryClient.setQueryData(["settings"], { ...prefs, ...patch });
  };

  return (
    <div className="flex w-full max-w-3xl flex-col gap-6">
      <div>
        <h1 className="font-display text-[clamp(1.9rem,2.6vw,2.9rem)] font-medium tracking-tight">Settings</h1>
        <p className="mt-1 text-sm text-muted-foreground">Defaults for the next upload, and how long files are kept.</p>
      </div>
      {query.isError ? <p className="text-sm text-destructive">{(query.error as Error).message}</p> : null}
      {!prefs ? (
        <div className="space-y-3">
          <Skeleton className="h-28 w-full" />
          <Skeleton className="h-28 w-full" />
          <Skeleton className="h-28 w-full" />
        </div>
      ) : null}
      {prefs ? (
        <>
      <Card>
        <CardHeader>
          <CardTitle>Default mode</CardTitle>
          <CardDescription>Pre-selected when you open the upload panel.</CardDescription>
        </CardHeader>
        <CardContent>
          <Select value={prefs.defaultMode} onValueChange={(value) => update({ defaultMode: value as DocumentMode })}>
            <SelectTrigger aria-label="Default mode">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {DOCUMENT_MODES.map((mode) => (
                <SelectItem key={mode.id} value={mode.id}>
                  {mode.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Safe mode</CardTitle>
          <CardDescription>On by default so summaries stay on redacted text.</CardDescription>
        </CardHeader>
        <CardContent className="flex items-center gap-3">
          <Switch checked={prefs.safeMode} onCheckedChange={(safeMode) => update({ safeMode })} id="default-safe-mode" />
          <label htmlFor="default-safe-mode" className="text-sm">
            {prefs.safeMode ? "On" : "Off"}
          </label>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Keep documents</CardTitle>
          <CardDescription>Older files are removed on this schedule. Recent uploads stay.</CardDescription>
        </CardHeader>
        <CardContent>
          <Select value={String(prefs.retentionDays)} onValueChange={(value) => update({ retentionDays: Number(value) })}>
            <SelectTrigger aria-label="Retention">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="7">7 days</SelectItem>
              <SelectItem value="30">30 days</SelectItem>
              <SelectItem value="90">90 days</SelectItem>
            </SelectContent>
          </Select>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Store detected text</CardTitle>
          <CardDescription>Off keeps only the masked value. A deployment can still refuse to store the original.</CardDescription>
        </CardHeader>
        <CardContent className="flex items-center gap-3">
          <Switch
            checked={prefs.storeRawDetections}
            onCheckedChange={(storeRawDetections) => update({ storeRawDetections })}
            id="store-raw"
          />
          <label htmlFor="store-raw" className="text-sm">
            {prefs.storeRawDetections ? "On" : "Off"}
          </label>
        </CardContent>
      </Card>
      <Button className="self-start" disabled={save.isPending} onClick={() => save.mutate(prefs)}>
        Save
      </Button>
      <Card>
        <CardHeader>
          <CardTitle>Delete all my data</CardTitle>
          <CardDescription>Removes your files, detections, exports, and activity. This cannot be undone.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          {confirming ? (
            <>
              <Button variant="destructive" disabled={wipe.isPending} onClick={() => wipe.mutate()}>
                Delete everything
              </Button>
              <Button variant="outline" onClick={() => setConfirming(false)}>
                Cancel
              </Button>
            </>
          ) : (
            <Button variant="outline" onClick={() => setConfirming(true)}>
              Delete all my data
            </Button>
          )}
        </CardContent>
      </Card>
        </>
      ) : null}
    </div>
  );
}

"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Info } from "lucide-react";
import { useEffect, useState } from "react";
import { useDropzone } from "react-dropzone";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Switch } from "@/components/ui/switch";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { ApiError, completeIngest, createDocument, uploadWithProgress } from "@/lib/api";
import { getSettings } from "@/lib/api/settings";
import { DOCUMENT_MODES } from "@/lib/modes";
import { useApiToken } from "@/lib/review/token";
import type { DocumentMode } from "@/lib/types";
import { cn } from "@/lib/utils";

interface QueueItem {
  id: string;
  name: string;
  progress: number;
  state: "queued" | "uploading" | "done" | "error";
  message?: string;
}

async function uploadOne(token: string, file: File, mode: DocumentMode, safeMode: boolean, onProgress: (value: number) => void) {
  const created = await createDocument(token, {
    filename: file.name,
    contentType: "application/pdf",
    mode,
    safeMode,
    sizeBytes: file.size,
  });
  await uploadWithProgress(created.presignedPutUrl, file, onProgress);
  await completeIngest(token, created.id);
}

export function UploadPanel() {
  const getToken = useApiToken();
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<DocumentMode>("resume_anonymization");
  const [safeMode, setSafeMode] = useState(true);
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const settingsQuery = useQuery({
    queryKey: ["settings"],
    queryFn: async () => getSettings(await getToken()),
  });

  useEffect(() => {
    if (!settingsQuery.data) {
      return;
    }
    setMode(settingsQuery.data.defaultMode);
    setSafeMode(settingsQuery.data.safeMode);
  }, [settingsQuery.data]);

  const uploadMutation = useMutation({
    mutationFn: async (files: File[]) => {
      for (const file of files) {
        const id = `${file.name}-${file.size}-${file.lastModified}`;
        setQueue((current) => current.map((item) => (item.id === id ? { ...item, state: "uploading", progress: 0 } : item)));
        try {
          await uploadOne(await getToken(), file, mode, safeMode, (progress) => {
            setQueue((current) => current.map((item) => (item.id === id ? { ...item, progress } : item)));
          });
          setQueue((current) => current.map((item) => (item.id === id ? { ...item, state: "done", progress: 100 } : item)));
          toast.success(`${file.name} uploaded`);
        } catch (error) {
          const message = error instanceof ApiError || error instanceof Error ? error.message : "Upload failed";
          setQueue((current) => current.map((item) => (item.id === id ? { ...item, state: "error", message } : item)));
          toast.error(`${file.name}: ${message}`);
        }
      }
    },
    onSettled: async () => {
      await queryClient.invalidateQueries({ queryKey: ["documents"] });
    },
  });

  const dropzone = useDropzone({
    accept: { "application/pdf": [".pdf"] },
    multiple: true,
    disabled: uploadMutation.isPending,
    onDrop: (accepted) => {
      if (accepted.length === 0) {
        toast.error("Only PDF files can be uploaded.");
        return;
      }
      setQueue(
        accepted.map((file) => ({
          id: `${file.name}-${file.size}-${file.lastModified}`,
          name: file.name,
          progress: 0,
          state: "queued",
        })),
      );
      uploadMutation.mutate(accepted);
    },
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Upload</CardTitle>
        <CardDescription>Drag in one or more PDFs. Progress is the bytes actually sent.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-1 gap-2 md:grid-cols-6">
          {DOCUMENT_MODES.map((item, index) => {
            const Icon = item.icon;
            const selected = mode === item.id;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => setMode(item.id)}
                className={cn(
                  "rounded-lg border p-3 text-left transition-[color,background-color,border-color,transform] duration-200 md:col-span-2",
                  index === 3 && "md:col-start-2",
                  selected ? "border-primary bg-accent" : "hover:bg-muted",
                )}
              >
                <div className="flex items-center gap-2 text-sm font-medium">
                  <Icon className="h-4 w-4 text-primary" />
                  {item.label}
                </div>
                <p className="mt-1 text-xs text-muted-foreground">{item.description}</p>
              </button>
            );
          })}
        </div>
        <div className="flex items-center gap-2">
          <Switch id="safe-mode" checked={safeMode} onCheckedChange={setSafeMode} />
          <label htmlFor="safe-mode" className="text-sm">
            Safe mode
          </label>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button type="button" variant="ghost" size="icon" aria-label="What safe mode does">
                <Info className="h-4 w-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Summaries use redacted text when safe mode is on.</TooltipContent>
          </Tooltip>
        </div>
        <div
          {...dropzone.getRootProps()}
          className={cn(
            "flex cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed px-4 py-10 text-center",
            dropzone.isDragActive ? "border-primary bg-accent" : "border-border",
          )}
        >
          <input {...dropzone.getInputProps()} />
          <p className="text-sm font-medium">Drop PDFs here, or click to choose files</p>
          <p className="mt-1 text-xs text-muted-foreground">PDF only. Several files upload one after another.</p>
        </div>
        {queue.length > 0 ? (
          <ul className="space-y-3">
            {queue.map((item) => (
              <li key={item.id} className="space-y-1">
                <div className="flex items-center justify-between text-sm">
                  <span className="truncate pr-3">{item.name}</span>
                  <span className="text-muted-foreground">
                    {item.state === "error" ? "Failed" : item.state === "done" ? "Done" : `${item.progress}%`}
                  </span>
                </div>
                <Progress value={item.state === "error" ? 0 : item.progress} />
                {item.message ? <p className="text-xs text-destructive">{item.message}</p> : null}
              </li>
            ))}
          </ul>
        ) : null}
      </CardContent>
    </Card>
  );
}

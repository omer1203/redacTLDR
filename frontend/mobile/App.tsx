import { StatusBar } from 'expo-status-bar';
import * as DocumentPicker from 'expo-document-picker';
import React, { useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query';

// Use LAN IP when testing on device (e.g. EXPO_PUBLIC_API_URL=http://192.168.1.x:8000)
const HOST = process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8000';

const client = new QueryClient();

function HealthCheck() {
  const { data, error, isLoading } = useQuery({
    queryKey: ['health'],
    queryFn: async () => {
      const response = await fetch(`${HOST}/v1/health`);
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      return response.json();
    },
  });

  if (isLoading) return <Text>Loading...</Text>;
  if (error) return <Text style={styles.error}>Error: {(error as Error).message}</Text>;
  return <Text>API says: {JSON.stringify(data)}</Text>;
}

function UploadFlow() {
  const [status, setStatus] = useState<string>('');
  const [docId, setDocId] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  const pickAndUpload = async () => {
    setUploading(true);
    setStatus('Picking file...');
    // flow: pick → create doc → PUT to S3 → ingestDone. Content-Type must match what we signed.

    try {
      const result = await DocumentPicker.getDocumentAsync({
        type: 'application/pdf',
        copyToCacheDirectory: true,
      });

      if (result.canceled) {
        setStatus('Cancelled');
        setUploading(false);
        return;
      }

      const file = result.assets[0];
      const filename = file.name;
      const contentType = file.mimeType || 'application/pdf';

      setStatus('Getting upload URL...');

      const createRes = await fetch(`${HOST}/v1/documents`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename, contentType }),
      });

      if (!createRes.ok) {
        const errText = await createRes.text();
        throw new Error(`Create failed: ${createRes.status} ${errText}`);
      }

      const { id, presignedPutUrl } = await createRes.json();
      setDocId(id);
      setStatus('Uploading to S3...');

      const blob = await (await fetch(file.uri)).blob();
      const putRes = await fetch(presignedPutUrl, {
        method: 'PUT',
        headers: { 'Content-Type': contentType },
        body: blob,
      });

      if (!putRes.ok) {
        throw new Error(`S3 upload failed: ${putRes.status}. Check Content-Type matches.`);
      }

      setStatus('Finalizing...');

      const ingestRes = await fetch(`${HOST}/v1/documents/${id}/ingestDone`, {
        method: 'POST',
      });

      if (!ingestRes.ok) {
        throw new Error(`Ingest failed: ${ingestRes.status}`);
      }

      const ingestData = await ingestRes.json();
      setStatus(`Done: ${ingestData.status}`);
    } catch (e) {
      setStatus(`Error: ${(e as Error).message}`);
      Alert.alert('Upload failed', (e as Error).message);
    } finally {
      setUploading(false);
    }
  };

  return (
    <View style={styles.uploadSection}>
      <TouchableOpacity
        style={[styles.button, uploading && styles.buttonDisabled]}
        onPress={pickAndUpload}
        disabled={uploading}
      >
        {uploading ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.buttonText}>Pick PDF & Upload</Text>
        )}
      </TouchableOpacity>
      {status ? <Text style={styles.status}>{status}</Text> : null}
      {docId ? <Text style={styles.docId}>Doc ID: {docId}</Text> : null}
    </View>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={client}>
      <SafeAreaView style={styles.container}>
        <ScrollView contentContainerStyle={styles.scroll}>
          <View style={styles.section}>
            <Text style={styles.title}>redactldr</Text>
            <Text style={styles.subtitle}>Health Check</Text>
            <HealthCheck />
          </View>
          <View style={styles.section}>
            <Text style={styles.subtitle}>Upload PDF</Text>
            <UploadFlow />
          </View>
          <StatusBar style="auto" />
        </ScrollView>
      </SafeAreaView>
    </QueryClientProvider>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f5f5f5' },
  scroll: { padding: 16, paddingBottom: 48 },
  section: { marginBottom: 24 },
  title: { fontSize: 24, fontWeight: '700', marginBottom: 4 },
  subtitle: { fontSize: 16, fontWeight: '600', marginBottom: 8 },
  error: { color: 'red' },
  uploadSection: { gap: 8 },
  button: {
    backgroundColor: '#007AFF',
    paddingVertical: 12,
    paddingHorizontal: 20,
    borderRadius: 8,
    alignItems: 'center',
  },
  buttonDisabled: { opacity: 0.7 },
  buttonText: { color: '#fff', fontWeight: '600' },
  status: { fontSize: 14 },
  docId: { fontSize: 12, color: '#666', fontFamily: 'monospace' },
});

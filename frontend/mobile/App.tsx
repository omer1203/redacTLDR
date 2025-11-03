import { StatusBar } from 'expo-status-bar';
import React from 'react';
import { SafeAreaView, Text, View } from 'react-native';
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query';

// Use environment variable or fallback to localhost
const HOST = process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8000';

const client = new QueryClient(); // create a query client instance

// function for small component that calls GET /v1/health endpoint and displays the response/renders the JSON
function HealthCheck() {
    const { data, error, isLoading } = useQuery({ 
        queryKey: ['health'],
        queryFn: async () => { 
            const response = await fetch(`${HOST}/v1/health`);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            return response.json();
        },
    });

    if(isLoading) return <Text>Loading...</Text>;
    if(error) return <Text style = {{color: "red"}}>Error: {(error as Error).message}</Text>;
    return <Text>API says: {JSON.stringify(data)}</Text>;
}

//App root component that provides Reacty Query and renders the HealthCheck component
export default function App() { 
    return ( 
        <QueryClientProvider client={client}>
            <SafeAreaView style={{flex: 1, alignItems: 'center', justifyContent: 'center'}}>
                <View style={{padding : 16}}>
                    <Text style={{fontSize: 20, fontWeight: '600', marginBottom: 8}}>
                        RedacTLDR API Health Check 1
                    </Text>
                    <HealthCheck />
                </View>
                <StatusBar style="auto" />
            </SafeAreaView>
        </QueryClientProvider>
    );
}
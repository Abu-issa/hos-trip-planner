import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || (import.meta.env.DEV ? 'http://localhost:8000' : ''),
  timeout: 90000,
  headers: { 'Content-Type': 'application/json' },
});

export async function planTrip(input) {
  const response = await api.post('/api/trips/plan/', input);
  return response.data;
}

import { supabase } from '$lib/supabase/client';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

type ResponseType = 'json' | 'blob';

interface RequestOptions {
	responseType?: ResponseType;
}

async function getToken(): Promise<string> {
	const { data } = await supabase.auth.getSession();
	const token = data.session?.access_token;
	if (!token) {
		throw new Error('Not authenticated. Please sign in.');
	}
	return token;
}

function buildUrl(path: string, params?: Record<string, string | number | boolean>): string {
	const url = new URL(path, API_BASE);
	if (params) {
		for (const [key, value] of Object.entries(params)) {
			if (value !== undefined && value !== null) {
				url.searchParams.set(key, String(value));
			}
		}
	}
	return url.toString();
}

async function handleResponse(response: Response, responseType: ResponseType) {
	if (!response.ok) {
		let detail = `Request failed with status ${response.status}`;
		try {
			const body = await response.json();
			if (body?.detail) detail = body.detail;
		} catch {
			// Response body isn't JSON — keep the status-based message
		}
		throw new Error(detail);
	}
	return responseType === 'blob' ? response.blob() : response.json();
}

async function request(
	method: string,
	path: string,
	{
		params,
		body,
		responseType = 'json'
	}: {
		params?: Record<string, string | number | boolean>;
		body?: unknown;
		responseType?: ResponseType;
	} = {}
) {
	const token = await getToken();
	const url = buildUrl(path, params);

	const headers: Record<string, string> = {
		Authorization: `Bearer ${token}`
	};
	if (body !== undefined) {
		headers['Content-Type'] = 'application/json';
	}

	let response: Response;
	try {
		response = await fetch(url, {
			method,
			headers,
			body: body !== undefined ? JSON.stringify(body) : undefined
		});
	} catch (e) {
		throw new Error('Network error. Please check your connection and try again.');
	}

	return handleResponse(response, responseType);
}

export const apiClient = {
	get<T = unknown>(
		path: string,
		params?: Record<string, string | number | boolean>,
		options?: RequestOptions
	): Promise<T> {
		return request('GET', path, { params, responseType: options?.responseType });
	},

	post<T = unknown>(path: string, body?: unknown, options?: RequestOptions): Promise<T> {
		return request('POST', path, { body, responseType: options?.responseType });
	},

	put<T = unknown>(path: string, body?: unknown, options?: RequestOptions): Promise<T> {
		return request('PUT', path, { body, responseType: options?.responseType });
	},

	patch<T = unknown>(path: string, body?: unknown, options?: RequestOptions): Promise<T> {
		return request('PATCH', path, { body, responseType: options?.responseType });
	},

	delete<T = unknown>(path: string, options?: RequestOptions): Promise<T> {
		return request('DELETE', path, { responseType: options?.responseType });
	}
};

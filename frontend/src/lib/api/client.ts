import { supabase } from '$lib/supabase/client';
import type { ApiEndpoints, ApiMethod, ApiRequest, ApiResponse } from '$lib/types/api';
import type { ApiError } from '$lib/types';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

type ResponseType = 'json' | 'blob';

interface RequestOptions {
	responseType?: ResponseType;
}

/**
 * Parse API error response into structured ApiError
 */
function parseApiError(status: number, body: unknown): ApiError {
	const error: ApiError = {
		name: 'ApiError',
		message: `HTTP ${status}`,
		status,
		code: `HTTP_${status}`,
		detail: `Request failed with status ${status}`,
		timestamp: new Date().toISOString(),
	};

	if (body && typeof body === 'object') {
		const err = body as Record<string, unknown>;
		if (typeof err.detail === 'string') {
			error.detail = err.detail;
		}
		if (typeof err.code === 'string') {
			error.code = err.code;
		}
	}

	return error;
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
		let body: unknown;
		try {
			body = await response.json();
		} catch {
			// Response body isn't JSON
		}
		const error = parseApiError(response.status, body);
		throw error;
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
		const error: ApiError = {
			name: 'ApiError',
			message: 'Network error',
			status: 0,
			code: 'NETWORK_ERROR',
			detail: 'Network error. Please check your connection and try again.',
			timestamp: new Date().toISOString()
		};
		throw error;
	}

	return handleResponse(response, responseType);
}

export const apiClient = {
	/**
	 * GET request with optional query parameters
	 * @example
	 * const logs = await apiClient.get('/api/symptoms/logs', { limit: 50 });
	 */
	get<T extends ApiMethod>(
		path: T,
		params?: Record<string, string | number | boolean | undefined>,
		options?: RequestOptions
	): Promise<ApiResponse<T>> {
		return request('GET', path, { params: params as Record<string, string | number | boolean>, responseType: options?.responseType });
	},

	/**
	 * POST request with body
	 * @example
	 * const response = await apiClient.post('/api/chat', { message: 'Hello' });
	 */
	post<T extends ApiMethod>(
		path: T,
		body?: ApiRequest<T>,
		options?: RequestOptions
	): Promise<ApiResponse<T>> {
		return request('POST', path, { body, responseType: options?.responseType });
	},

	/**
	 * PUT request with body
	 */
	put<T extends ApiMethod>(
		path: T,
		body?: ApiRequest<T>,
		options?: RequestOptions
	): Promise<ApiResponse<T>> {
		return request('PUT', path, { body, responseType: options?.responseType });
	},

	/**
	 * PATCH request with body
	 */
	patch<T extends ApiMethod>(
		path: T,
		body?: ApiRequest<T>,
		options?: RequestOptions
	): Promise<ApiResponse<T>> {
		return request('PATCH', path, { body, responseType: options?.responseType });
	},

	/**
	 * DELETE request
	 */
	delete<T extends ApiMethod>(
		path: T,
		options?: RequestOptions
	): Promise<ApiResponse<T>> {
		return request('DELETE', path, { responseType: options?.responseType });
	}
};

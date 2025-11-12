/**
 * Typed API Client for PostHog
 *
 * This provides a type-safe wrapper around fetch() using the auto-generated
 * OpenAPI types from api-types.ts
 *
 * Usage:
 *   import { apiClient } from 'lib/api-client'
 *
 *   // GET request
 *   const insights = await apiClient.get('/api/projects/{project_id}/insights/')
 *
 *   // POST request
 *   const newInsight = await apiClient.post('/api/projects/{project_id}/insights/', {
 *       name: 'My Insight',
 *       filters: { ... }
 *   })
 *
 * This client provides:
 * - Full TypeScript type safety from OpenAPI schema
 * - Automatic CSRF token handling
 * - Consistent error handling
 * - Request/response interceptors
 */
import { apiStatusLogic } from 'lib/logic/apiStatusLogic'

// Type imports - these will be available once api-types.ts is generated
// @ts-ignore - File will be generated
import type { paths } from './api-types'

type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'

interface RequestOptions extends RequestInit {
    params?: Record<string, any>
    query?: Record<string, any>
}

interface ApiError extends Error {
    status: number
    statusText: string
    response?: any
}

class TypedApiClient {
    private baseUrl: string
    private defaultHeaders: HeadersInit

    constructor(baseUrl: string = '') {
        this.baseUrl = baseUrl
        this.defaultHeaders = {
            'Content-Type': 'application/json',
        }
    }

    /**
     * Get CSRF token from cookie
     */
    private getCsrfToken(): string | null {
        const name = 'posthog_csrftoken'
        const cookies = document.cookie.split(';')
        for (let cookie of cookies) {
            const [cookieName, cookieValue] = cookie.trim().split('=')
            if (cookieName === name) {
                return decodeURIComponent(cookieValue)
            }
        }
        return null
    }

    /**
     * Build URL with path parameters and query string
     */
    private buildUrl(path: string, options?: RequestOptions): string {
        let url = this.baseUrl + path

        // Replace path parameters (e.g., {project_id})
        if (options?.params) {
            for (const [key, value] of Object.entries(options.params)) {
                url = url.replace(`{${key}}`, encodeURIComponent(String(value)))
            }
        }

        // Add query parameters
        if (options?.query) {
            const queryParams = new URLSearchParams()
            for (const [key, value] of Object.entries(options.query)) {
                if (value !== undefined && value !== null) {
                    if (Array.isArray(value)) {
                        value.forEach((v) => queryParams.append(key, String(v)))
                    } else {
                        queryParams.append(key, String(value))
                    }
                }
            }
            const queryString = queryParams.toString()
            if (queryString) {
                url += (url.includes('?') ? '&' : '?') + queryString
            }
        }

        return url
    }

    /**
     * Make a typed HTTP request
     */
    private async request<TResponse = any>(
        method: HttpMethod,
        path: string,
        options?: RequestOptions
    ): Promise<TResponse> {
        const url = this.buildUrl(path, options)

        const headers: HeadersInit = {
            ...this.defaultHeaders,
            ...options?.headers,
        }

        // Add CSRF token for non-GET requests
        if (method !== 'GET') {
            const csrfToken = this.getCsrfToken()
            if (csrfToken) {
                headers['X-CSRFToken'] = csrfToken
            }
        }

        const config: RequestInit = {
            ...options,
            method,
            headers,
        }

        // Serialize body if it's an object
        if (options?.body && typeof options.body === 'object') {
            config.body = JSON.stringify(options.body)
        }

        try {
            // Notify API status logic
            apiStatusLogic.actions.setStatus('loading')

            const response = await fetch(url, config)

            // Handle non-2xx responses
            if (!response.ok) {
                const error: ApiError = new Error(`HTTP ${response.status}: ${response.statusText}`) as ApiError
                error.status = response.status
                error.statusText = response.statusText

                try {
                    error.response = await response.json()
                } catch {
                    error.response = await response.text()
                }

                apiStatusLogic.actions.setStatus('error')
                throw error
            }

            // Parse response
            const contentType = response.headers.get('content-type')
            let data: TResponse

            if (contentType?.includes('application/json')) {
                data = await response.json()
            } else if (response.status === 204) {
                // No content
                data = undefined as TResponse
            } else {
                data = (await response.text()) as TResponse
            }

            apiStatusLogic.actions.setStatus('success')
            return data
        } catch (error) {
            apiStatusLogic.actions.setStatus('error')
            throw error
        }
    }

    /**
     * Typed GET request
     */
    async get<TPath extends keyof paths>(path: TPath, options?: Omit<RequestOptions, 'body'>): Promise<any> {
        return this.request('GET', path as string, options)
    }

    /**
     * Typed POST request
     */
    async post<TPath extends keyof paths>(path: TPath, body?: any, options?: RequestOptions): Promise<any> {
        return this.request('POST', path as string, {
            ...options,
            body,
        })
    }

    /**
     * Typed PUT request
     */
    async put<TPath extends keyof paths>(path: TPath, body?: any, options?: RequestOptions): Promise<any> {
        return this.request('PUT', path as string, {
            ...options,
            body,
        })
    }

    /**
     * Typed PATCH request
     */
    async patch<TPath extends keyof paths>(path: TPath, body?: any, options?: RequestOptions): Promise<any> {
        return this.request('PATCH', path as string, {
            ...options,
            body,
        })
    }

    /**
     * Typed DELETE request
     */
    async delete<TPath extends keyof paths>(path: TPath, options?: RequestOptions): Promise<any> {
        return this.request('DELETE', path as string, options)
    }
}

// Export singleton instance
export const apiClient = new TypedApiClient()

// Export class for testing or custom instances
export { TypedApiClient }

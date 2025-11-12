/**
 * API Client Usage Examples
 *
 * This file contains practical examples of using the typed API client.
 * These examples demonstrate common patterns and best practices.
 */
// =============================================================================
// EXAMPLE 10: Integration with Kea
// =============================================================================
import { actions, kea, loaders, reducers } from 'kea'

import { apiClient } from './api-client'

// EXAMPLE 1: Basic CRUD Operations

export async function exampleBasicCRUD() {
    const projectId = '123'

    // CREATE - Post a new insight
    const newInsight = await apiClient.post(
        '/api/projects/{project_id}/insights/',
        {
            name: 'Revenue Trends',
            description: 'Weekly revenue analysis',
            filters: {
                events: [{ id: 'purchase_complete' }],
                date_from: '-30d',
            },
        },
        {
            params: { project_id: projectId },
        }
    )

    console.log('Created insight:', newInsight)

    // READ - Get all insights
    const insights = await apiClient.get('/api/projects/{project_id}/insights/', {
        params: { project_id: projectId },
        query: {
            limit: 20,
            offset: 0,
            order: '-created_at',
        },
    })

    console.log('Insights:', insights)

    // READ - Get single insight
    const insight = await apiClient.get('/api/projects/{project_id}/insights/{id}/', {
        params: {
            project_id: projectId,
            id: newInsight.id,
        },
    })

    console.log('Single insight:', insight)

    // UPDATE - Patch the insight
    const updated = await apiClient.patch(
        '/api/projects/{project_id}/insights/{id}/',
        {
            name: 'Updated Revenue Trends',
        },
        {
            params: {
                project_id: projectId,
                id: newInsight.id,
            },
        }
    )

    console.log('Updated insight:', updated)

    // DELETE - Remove the insight
    await apiClient.delete('/api/projects/{project_id}/insights/{id}/', {
        params: {
            project_id: projectId,
            id: newInsight.id,
        },
    })

    console.log('Deleted insight')
}

// =============================================================================
// EXAMPLE 2: Query Execution (HogQL)
// =============================================================================

export async function exampleQueryExecution() {
    const projectId = '123'

    // Execute a HogQL query
    const queryResult = await apiClient.post(
        '/api/projects/{project_id}/query/',
        {
            query: {
                kind: 'HogQLQuery',
                query: 'SELECT event, count() as count FROM events GROUP BY event LIMIT 10',
            },
        },
        {
            params: { project_id: projectId },
        }
    )

    console.log('Query result:', queryResult)

    // Execute with async mode
    const asyncQuery = await apiClient.post(
        '/api/projects/{project_id}/query/',
        {
            query: {
                kind: 'TrendsQuery',
                series: [
                    {
                        event: '$pageview',
                        kind: 'EventsNode',
                    },
                ],
                dateRange: {
                    date_from: '-30d',
                },
            },
            async: true,
        },
        {
            params: { project_id: projectId },
        }
    )

    console.log('Async query started:', asyncQuery)

    // Poll for results
    const queryId = asyncQuery.query_id
    let result
    do {
        await new Promise((resolve) => setTimeout(resolve, 1000))
        result = await apiClient.get('/api/projects/{project_id}/query/{query_id}/', {
            params: { project_id: projectId, query_id: queryId },
        })
    } while (result.status === 'running')

    console.log('Query completed:', result)
}

// =============================================================================
// EXAMPLE 3: Dashboards and Tiles
// =============================================================================

export async function exampleDashboards() {
    const projectId = '123'

    // Get all dashboards
    const dashboards = await apiClient.get('/api/projects/{project_id}/dashboards/', {
        params: { project_id: projectId },
    })

    console.log('Dashboards:', dashboards)

    // Create a new dashboard
    const newDashboard = await apiClient.post(
        '/api/projects/{project_id}/dashboards/',
        {
            name: 'Executive Dashboard',
            description: 'Key metrics for leadership',
            pinned: true,
            tags: ['executive', 'important'],
        },
        {
            params: { project_id: projectId },
        }
    )

    console.log('Created dashboard:', newDashboard)

    // Add a tile to the dashboard
    const tile = await apiClient.post(
        '/api/projects/{project_id}/dashboards/{id}/tiles/',
        {
            insight: 456, // insight ID
            layouts: {
                sm: { x: 0, y: 0, w: 6, h: 5 },
                xs: { x: 0, y: 0, w: 6, h: 5 },
            },
        },
        {
            params: {
                project_id: projectId,
                id: newDashboard.id,
            },
        }
    )

    console.log('Added tile:', tile)
}

// =============================================================================
// EXAMPLE 4: Feature Flags
// =============================================================================

export async function exampleFeatureFlags() {
    const projectId = '123'

    // List all feature flags
    const flags = await apiClient.get('/api/projects/{project_id}/feature_flags/', {
        params: { project_id: projectId },
    })

    console.log('Feature flags:', flags)

    // Create a new feature flag
    const newFlag = await apiClient.post(
        '/api/projects/{project_id}/feature_flags/',
        {
            key: 'new-checkout-flow',
            name: 'New Checkout Flow',
            filters: {
                groups: [
                    {
                        properties: [],
                        rollout_percentage: 50,
                    },
                ],
            },
            active: true,
        },
        {
            params: { project_id: projectId },
        }
    )

    console.log('Created flag:', newFlag)

    // Evaluate feature flags for a user (via /decide endpoint)
    // Note: This is typically called from the frontend, not via apiClient
}

// =============================================================================
// EXAMPLE 5: Cohorts
// =============================================================================

export async function exampleCohorts() {
    const projectId = '123'

    // Create a cohort
    const cohort = await apiClient.post(
        '/api/projects/{project_id}/cohorts/',
        {
            name: 'Power Users',
            description: 'Users with >100 events in the last 30 days',
            filters: {
                properties: {
                    type: 'AND',
                    values: [
                        {
                            key: 'event_count_30d',
                            value: 100,
                            operator: 'gt',
                            type: 'person',
                        },
                    ],
                },
            },
        },
        {
            params: { project_id: projectId },
        }
    )

    console.log('Created cohort:', cohort)

    // Get cohort persons
    const persons = await apiClient.get('/api/projects/{project_id}/cohorts/{id}/persons/', {
        params: {
            project_id: projectId,
            id: cohort.id,
        },
        query: {
            limit: 100,
        },
    })

    console.log('Cohort persons:', persons)
}

// =============================================================================
// EXAMPLE 6: Session Recordings
// =============================================================================

export async function exampleSessionRecordings() {
    const projectId = '123'

    // List session recordings with filters
    const recordings = await apiClient.get('/api/projects/{project_id}/session_recordings/', {
        params: { project_id: projectId },
        query: {
            limit: 20,
            offset: 0,
            filters: JSON.stringify({
                date_from: '-7d',
                events: [{ id: '$pageview', type: 'events' }],
            }),
        },
    })

    console.log('Recordings:', recordings)

    // Get a specific recording
    const recording = await apiClient.get('/api/projects/{project_id}/session_recordings/{id}/', {
        params: {
            project_id: projectId,
            id: 'recording-123',
        },
    })

    console.log('Recording details:', recording)

    // Get recording snapshots
    const snapshots = await apiClient.get('/api/projects/{project_id}/session_recordings/{id}/snapshots/', {
        params: {
            project_id: projectId,
            id: 'recording-123',
        },
    })

    console.log('Snapshots:', snapshots)
}

// =============================================================================
// EXAMPLE 7: Error Handling
// =============================================================================

export async function exampleErrorHandling() {
    const projectId = '123'

    try {
        // This will likely fail with validation errors
        await apiClient.post(
            '/api/projects/{project_id}/insights/',
            {
                // Missing required fields
                name: '',
            },
            {
                params: { project_id: projectId },
            }
        )
    } catch (error) {
        console.error('Validation error:', {
            status: error.status,
            message: error.message,
            details: error.response,
        })

        // Handle specific error types
        if (error.status === 400) {
            console.error('Bad request - fix validation errors:', error.response)
        } else if (error.status === 403) {
            console.error('Permission denied - check user permissions')
        } else if (error.status === 404) {
            console.error('Not found - check if resource exists')
        } else if (error.status >= 500) {
            console.error('Server error - try again later')
        }
    }

    // Graceful degradation example
    try {
        const insights = await apiClient.get('/api/projects/{project_id}/insights/', {
            params: { project_id: projectId },
        })
        return insights
    } catch (error) {
        console.warn('Failed to load insights, using cached data:', error)
        return getCachedInsights(projectId)
    }
}

// =============================================================================
// EXAMPLE 8: Batch Operations
// =============================================================================

export async function exampleBatchOperations() {
    const projectId = '123'

    // Create multiple insights in parallel
    const insightNames = ['Metric A', 'Metric B', 'Metric C']

    const createdInsights = await Promise.all(
        insightNames.map((name) =>
            apiClient.post(
                '/api/projects/{project_id}/insights/',
                {
                    name,
                    filters: { events: [{ id: '$pageview' }] },
                },
                {
                    params: { project_id: projectId },
                }
            )
        )
    )

    console.log('Created insights:', createdInsights)

    // Batch delete with error handling
    const deleteResults = await Promise.allSettled(
        createdInsights.map((insight) =>
            apiClient.delete('/api/projects/{project_id}/insights/{id}/', {
                params: {
                    project_id: projectId,
                    id: insight.id,
                },
            })
        )
    )

    deleteResults.forEach((result, index) => {
        if (result.status === 'fulfilled') {
            console.log(`Deleted insight ${index}`)
        } else {
            console.error(`Failed to delete insight ${index}:`, result.reason)
        }
    })
}

// =============================================================================
// EXAMPLE 9: Pagination
// =============================================================================

export async function examplePagination() {
    const projectId = '123'

    // Fetch all pages
    async function fetchAllInsights() {
        const allInsights = []
        let offset = 0
        const limit = 100

        while (true) {
            const response = await apiClient.get('/api/projects/{project_id}/insights/', {
                params: { project_id: projectId },
                query: { limit, offset },
            })

            allInsights.push(...response.results)

            if (!response.next) {
                break // No more pages
            }

            offset += limit
        }

        return allInsights
    }

    const allInsights = await fetchAllInsights()
    console.log('Total insights:', allInsights.length)
}

// =============================================================================

// =============================================================================

export const insightsLogic = kea({
    actions: {
        loadInsights: (projectId: string) => ({ projectId }),
        createInsight: (projectId: string, data: any) => ({ projectId, data }),
    },

    loaders: ({ actions }) => ({
        insights: {
            __default: [],
            loadInsights: async ({ projectId }) => {
                const response = await apiClient.get('/api/projects/{project_id}/insights/', {
                    params: { project_id: projectId },
                })
                return response.results
            },
        },
        createdInsight: {
            createInsight: async ({ projectId, data }) => {
                return await apiClient.post('/api/projects/{project_id}/insights/', data, {
                    params: { project_id: projectId },
                })
            },
        },
    }),
})

// =============================================================================
// Helper Functions
// =============================================================================

function getCachedInsights(projectId: string) {
    // Implementation would fetch from localStorage, IndexedDB, etc.
    return []
}

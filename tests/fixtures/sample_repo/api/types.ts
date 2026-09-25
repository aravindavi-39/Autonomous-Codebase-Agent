/**
 * TypeScript type definitions for the API.
 */

export interface User {
    id: number;
    username: string;
    email: string;
    createdAt: string;
}

export interface Post {
    id: number;
    title: string;
    body: string;
    authorId: number;
    createdAt: string;
}

export type ApiResponse<T> = {
    data: T;
    status: number;
};

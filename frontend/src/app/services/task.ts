import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { Task, TaskCreateRequest, TaskUpdateRequest } from '../models/task';

@Injectable({
  providedIn: 'root'
})
export class TaskService {
  private http = inject(HttpClient);
  private apiUrl = 'http://localhost:8000/api';

  // GET: Obtener todas las tareas
  getTasks(): Observable<Task[]> {
    return this.http.get<Task[]>(`${this.apiUrl}/tasks`);
  }

  // POST: Enviar texto a la IA para crear tarea
  processTask(text: string): Observable<Task> {
    const payload: TaskCreateRequest = { text };
    return this.http.post<Task>(`${this.apiUrl}/process-task`, payload);
  }

  // PATCH: Cambiar estado (completed)
  toggleTaskStatus(id: number, completed: boolean): Observable<Task> {
    return this.http.patch<Task>(`${this.apiUrl}/tasks/${id}/toggle`, { completed });
  }

  // PUT: Actualización manual
  updateTask(id: number, taskData: TaskUpdateRequest): Observable<Task> {
    return this.http.put<Task>(`${this.apiUrl}/tasks/${id}`, taskData);
  }

  // DELETE: Eliminar tarea
  deleteTask(id: number): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/tasks/${id}`);
  }
}

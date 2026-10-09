import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Router } from '@angular/router';
import { Observable, tap } from 'rxjs';
import { UserRegister, AuthResponse } from '../models/auth';

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private http = inject(HttpClient);
  private router = inject(Router);
  private apiUrl = 'http://127.0.0.1:8000/api'; // Ajusta la URL de tu servidor Uvicorn

  register(userData: UserRegister): Observable<any> {
    return this.http.post(`${this.apiUrl}/auth/register`, userData);
  }

  login(email: string, password: string): Observable<AuthResponse> {
    const body = new URLSearchParams();
    body.set('username', email); // OAuth2 en FastAPI usa 'username'
    body.set('password', password);

    const headers = new HttpHeaders({
      'Content-Type': 'application/x-www-form-urlencoded'
    });

    return this.http.post<AuthResponse>(`${this.apiUrl}/auth/login`, body.toString(), { headers }).pipe(
      tap((response) => {
        if (response.access_token) {
          localStorage.setItem('access_token', response.access_token);
        }
      })
    );
  }

  // Elimina el token de sesión y redirige inmediatamente a la Landing Page
  logout(): void {
    localStorage.removeItem('access_token');
    this.router.navigate(['/']);
  }

  getToken(): string | null {
    return localStorage.getItem('access_token');
  }

  isAuthenticated(): boolean {
    return !!this.getToken();
  }
}

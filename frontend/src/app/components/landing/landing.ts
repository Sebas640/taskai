import { Component, OnInit, OnDestroy, ViewEncapsulation, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { FlipSoundService } from '../../services/flip-sound';

interface Slide {
  image: string;
  title: string;
  description: string;
}

@Component({
  selector: 'app-landing',
  standalone: true,
  imports: [CommonModule, RouterModule],
  templateUrl: './landing.html',
  styleUrl: './landing.scss',
  encapsulation: ViewEncapsulation.None
})
export class LandingComponent implements OnInit, OnDestroy {
  // Sonido de volteo de las tarjetas de características
  readonly flipSound = inject(FlipSoundService);

  // Imágenes en alta definición de Unsplash
  slides: Slide[] = [
    {
      image: 'https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?q=80&w=1200&auto=format&fit=crop',
      title: 'Procesamiento de Lenguaje Natural',
      description: 'Escribe tus pendientes de forma natural y deja que la IA organice el trabajo.'
    },
    {
      image: 'https://images.unsplash.com/photo-1551288049-bebda4e38f71?q=80&w=1200&auto=format&fit=crop',
      title: 'Priorización Inteligente',
      description: 'Gemini analiza la urgencia y categoría de tus tareas automáticamente.'
    },
    {
      image: 'https://images.unsplash.com/photo-1507238691740-187a5b1d37b8?q=80&w=1200&auto=format&fit=crop',
      title: 'Control de Productividad',
      description: 'Panel despejado y métricas claras para dominar tu día a día.'
    }
  ];

  currentSlide = 0;
  autoSlideInterval: any;
  private observer!: IntersectionObserver;

  ngOnInit(): void {
    this.startAutoSlide();
    this.initScrollAnimations();
  }

  ngOnDestroy(): void {
    this.stopAutoSlide();
    if (this.observer) {
      this.observer.disconnect();
    }
  }

  // --- LÓGICA DEL CARRUSEL ---
  startAutoSlide(): void {
    this.autoSlideInterval = setInterval(() => {
      this.nextSlide();
    }, 4500);
  }

  stopAutoSlide(): void {
    if (this.autoSlideInterval) {
      clearInterval(this.autoSlideInterval);
    }
  }

  nextSlide(): void {
    this.currentSlide = (this.currentSlide + 1) % this.slides.length;
  }

  prevSlide(): void {
    this.currentSlide = (this.currentSlide - 1 + this.slides.length) % this.slides.length;
  }

  goToSlide(index: number): void {
    this.currentSlide = index;
    this.stopAutoSlide();
    this.startAutoSlide();
  }

  // --- ANIMACIONES AL HACER SCROLL ---
  initScrollAnimations(): void {
    setTimeout(() => {
      this.observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            entry.target.classList.add('visible');
          } else {
            entry.target.classList.remove('visible'); // Se oculta/muestra dinámicamente
          }
        });
      }, { threshold: 0.15 });

      document.querySelectorAll('.animate-on-scroll').forEach(el => {
        this.observer.observe(el);
      });
    }, 100);
  }
}

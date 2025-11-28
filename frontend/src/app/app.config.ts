import { ApplicationConfig, provideZoneChangeDetection } from '@angular/core';
import { provideHttpClient } from '@angular/common/http'; // ¡AGREGADO para DI de HttpClient!

export const appConfig: ApplicationConfig = {
  providers: [
    provideZoneChangeDetection({ eventCoalescing: true }), 
    // Provee el HttpClient globalmente
    provideHttpClient(), 
    // El 'routing' se ha quitado ya que no se usa en esta SPA.
  ]
};
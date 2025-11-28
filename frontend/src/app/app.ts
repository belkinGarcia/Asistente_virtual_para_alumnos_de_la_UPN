import { Component, OnInit } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';

export interface UserProfile { nombre: string; carrera: string; modalidad: 'Presencial'|'Virtual'|'Híbrido'; trabaja: boolean; horario_trabajo_inicio?: string; horario_trabajo_fin?: string; tiempo_transporte: number; transporte_tipo: 'Conducir'|'Transporte Público'|'Caminar/Bici'|'N/A'; carga_domestica: 'Alta (Vivo solo)'|'Media (Ayudo)'|'Baja (Vivo con padres)'; cronotipo: 'Mañana (Alondra)'|'Tarde'|'Noche (Búho)'; horas_sueno: number; resistencia_estudio: 'Baja (25min)'|'Media (45min)'|'Alta (90min)'; hora_dorada?: string; }

// --- CAMBIO AQUÍ: Añadimos 'hitos?' a la interfaz ---
export interface Milestone { titulo: string; descripcion: string; fecha_limite: string; completado: boolean; peso?: number; }
export interface ChatMessage { role: 'user'|'assistant'; text: string; horario?: any; hitos?: Milestone[]; }

export interface ExamItem { materia: string; fecha: string; hora: string; duracion: number; temas: string; dificultad: 'Alta'|'Media'|'Baja'; formato: 'Teórico'|'Práctico'|'Oral'|'Proyecto'; confianza: number; }
export interface DashboardStats { total_horas: number; sesiones_totales: number; promedio_energia: number; tasa_exito: number; materias_chart: any[]; energia_chart: any[]; nivel: number; xp_actual: number; xp_siguiente: number; racha_dias: number; logros: any[]; }
export interface FeedbackEstudio { materia: string; horas_reales: number; dificultad: string; nivel_energia: number; cumplio_objetivo: string; factor_bloqueo: string; calificacion?: number; dia_semana: string; horas_sueno: number; lugar_estudio: string; actividad_fisica: string; }
export interface Project { id: string; nombre: string; descripcion: string; fecha_fin: string; progreso: number; hitos: Milestone[]; }

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './app.html',
})
export class AppComponent implements OnInit {
  private apiUrl = 'http://127.0.0.1:5000/api';
  loading: boolean = false; hasProfile: boolean = false; step: number = 1; 
  isGoogleConnected: boolean = false;
  showEditModal: boolean = false; showExamModal: boolean = false; showDashboard: boolean = false; showCheckinModal: boolean = false; showPomodoroModal: boolean = false; showProjectsModal: boolean = false;
  isUpdating: boolean = false; isCrisisMode: boolean = false;

  profileData: UserProfile = { nombre: '', carrera: '', modalidad: 'Presencial', trabaja: false, horario_trabajo_inicio: '09:00', horario_trabajo_fin: '18:00', tiempo_transporte: 30, transporte_tipo: 'Transporte Público', carga_domestica: 'Media (Ayudo)', cronotipo: 'Tarde', horas_sueno: 7, resistencia_estudio: 'Media (45min)' };
  editData: UserProfile = { ...this.profileData }; 
  examsList: ExamItem[] = [];
  chatHistory: ChatMessage[] = [];
  userInput: string = '';
  stats: DashboardStats = { total_horas: 0, sesiones_totales: 0, promedio_energia: 0, tasa_exito: 0, materias_chart: [], energia_chart: [], nivel: 1, xp_actual: 0, xp_siguiente: 1000, racha_dias: 0, logros: [] };
  feedbackData: FeedbackEstudio = { materia: '', horas_reales: 1, dificultad: 'media', nivel_energia: 3, cumplio_objetivo: 'sí', factor_bloqueo: 'Ninguno', calificacion: undefined, dia_semana: 'Lunes', horas_sueno: 7, lugar_estudio: 'Casa', actividad_fisica: 'Ninguna' };
  listaMateriasSugeridas: string[] = [];
  listaLugares: string[] = ['Casa', 'Biblioteca UPN', 'Cafetería', 'Trabajo'];
  listaActividadFisica: string[] = ['Ninguna (Sedentario)', 'Caminata / Transporte', 'Gimnasio (Pesas/Fuerza)', 'Cardio Intenso (Correr/Fútbol)', 'Entrenamiento Ligero (Yoga/Estiramiento)'];
  projectsList: Project[] = [];
  newProjectData = { nombre: '', descripcion: '', fecha_fin: '' };
  activeProject: Project | null = null;
  timerRunning: boolean = false; timerMode: 'Focus'|'Break' = 'Focus'; timer: any = null; minutes: number = 25; seconds: number = 0; pomodoroMateria: string = '';
  xpGanado: number = 0; showXpAnim: boolean = false;

  constructor(private http: HttpClient) {}
  ngOnInit(): void { this.checkProfileStatus(); this.checkGoogleStatus(); }

  async checkGoogleStatus() { try { const res: any = await this.http.get(`${this.apiUrl}/google/status`).toPromise(); this.isGoogleConnected = res.conectado; } catch(e) { this.isGoogleConnected = false; } }
  async conectarGoogle() { this.loading = true; try { await this.http.get(`${this.apiUrl}/google/connect`).toPromise(); this.isGoogleConnected = true; alert("✅ ¡Conectado a Google Calendar con éxito!"); } catch(e) { alert("Error al conectar."); } finally { this.loading = false; } }
  async guardarEnCalendario(horario: any) { if (!this.isGoogleConnected) { if(confirm("No estás conectado. ¿Conectar?")) this.conectarGoogle(); return; } this.loading = true; try { const res: any = await this.http.post(`${this.apiUrl}/google/sync`, { horario }).toPromise(); alert(res.mensaje); this.triggerGamification(300); } catch(e) { alert("Error al sincronizar."); } finally { this.loading = false; } }

  async checkProfileStatus() { try { const res: any = await this.http.get(`${this.apiUrl}/check_perfil`).toPromise(); this.hasProfile = res.existe; if (this.hasProfile) { this.loadChatHistory(); this.loadProfileForEdit(false); } } catch (e) {} }
  async guardarPerfilInicial() { this.loading = true; try { await this.http.post(`${this.apiUrl}/crear_perfil`, this.profileData).toPromise(); this.hasProfile = true; this.loadChatHistory(); } catch(e){} finally { this.loading = false; } }
  async resetProfile() { if(confirm('⚠️ Reset total. ¿Continuar?')) { await this.http.post(`${this.apiUrl}/reset_perfil`, {}).toPromise(); window.location.reload(); } }
  async loadChatHistory() { try { const h: any = await this.http.get(`${this.apiUrl}/chat_history`).toPromise(); if (h) { this.chatHistory = h; this.scrollToBottom(); } } catch (e) {} }
  async enviarMensaje(silentSave: boolean = false) { if (!silentSave && (!this.userInput.trim() || this.loading)) return; if (!silentSave) { this.chatHistory.push({ role: 'user', text: this.userInput }); this.userInput = ''; this.loading = true; this.scrollToBottom(); } try { const res = await this.http.post<ChatMessage>(`${this.apiUrl}/conversar`, { history: this.chatHistory }).toPromise(); if (res && !silentSave) { this.chatHistory.push(res); this.scrollToBottom(); } } catch (e) { if (!silentSave) this.chatHistory.push({ role: 'assistant', text: 'Error.' }); } finally { this.loading = false; } }
  private scrollToBottom(): void { setTimeout(() => { const chatBody = document.querySelector('.chat-body'); if (chatBody) chatBody.scrollTop = chatBody.scrollHeight; }, 100); }
  
  async openDashboard() { this.loading = true; try { const data: any = await this.http.get(`${this.apiUrl}/dashboard_stats`).toPromise(); this.stats = data; this.showDashboard = true; } catch (e) {} finally { this.loading = false; } }
  closeDashboard() { this.showDashboard = false; }
  openExamModal() { this.examsList = []; this.addExamRow(); this.isCrisisMode = false; this.showExamModal = true; }
  closeExamModal() { this.showExamModal = false; }
  addExamRow() { const tomorrow = new Date(); tomorrow.setDate(tomorrow.getDate() + 1); this.examsList.push({ materia: '', fecha: tomorrow.toISOString().split('T')[0], hora: '08:00', duracion: 2, temas: '', dificultad: 'Alta', formato: 'Teórico', confianza: 50 }); }
  removeExamRow(i: number) { if (this.examsList.length > 1) this.examsList.splice(i, 1); }
  async generateExamPlan() { this.isUpdating = true; try { const ep = this.isCrisisMode ? '/planificar_crisis' : '/planificar_examenes'; const r:any = await this.http.post(`${this.apiUrl}${ep}`, {examenes:this.examsList}).toPromise(); this.showExamModal = false; this.chatHistory.push(r); this.enviarMensaje(true); } catch(e){} finally { this.isUpdating = false; } }
  async openCheckinModal() { this.cargarMaterias(); this.showCheckinModal = true; }
  closeCheckinModal() { this.showCheckinModal = false; }
  getDiaSemanaActual(): string { const dias = ['Domingo', 'Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado']; return dias[new Date().getDay()]; }
  async registrarSesion() { if(!this.feedbackData.materia) return; this.isUpdating = true; const diaAuto = this.getDiaSemanaActual(); const suenoAuto = this.profileData.horas_sueno || 7; try { await this.http.post(`${this.apiUrl}/registrar_historial`, { ...this.feedbackData, dia_semana: diaAuto, horas_sueno: suenoAuto, tipo_sesion: 'Manual' }).toPromise(); this.showCheckinModal = false; this.triggerGamification(150); this.chatHistory.push({role:'assistant', text:`✅ Registrado: ${this.feedbackData.materia}`}); this.enviarMensaje(true); } catch(e){} finally { this.isUpdating = false; this.feedbackData.materia = ''; this.feedbackData.nivel_energia = 3; } }
  
  getPreferredFocusTime(): number { const r = this.profileData.resistencia_estudio || 'Baja'; if (r.includes('Alta')) return 90; if (r.includes('Media')) return 45; return 25; }
  openPomodoroModal() { this.showPomodoroModal = true; this.resetTimer(this.getPreferredFocusTime()); this.cargarMaterias(); }
  closePomodoroModal() { this.pauseTimer(); this.showPomodoroModal = false; }
  toggleTimer() { if(this.timerRunning) this.pauseTimer(); else this.startTimer(); }
  startTimer() { if(!this.pomodoroMateria.trim() && this.timerMode==='Focus') { alert("Materia?"); return; } this.timerRunning=true; this.timer=setInterval(() => { if(this.seconds===0){ if(this.minutes===0) this.completePomodoro(); else {this.minutes--; this.seconds=59;} } else this.seconds--; }, 1000); }
  pauseTimer() { this.timerRunning=false; clearInterval(this.timer); }
  resetTimer(m: number) { this.pauseTimer(); this.minutes=m; this.seconds=0; this.timerMode = m <= 15 ? 'Break' : 'Focus'; }
  async completePomodoro() { this.pauseTimer(); if(this.timerMode==='Focus') { const d = this.getPreferredFocusTime() / 60; try { await this.http.post(`${this.apiUrl}/registrar_historial`, { materia:this.pomodoroMateria, horas_reales: d, tipo_sesion:'Pomodoro' }).toPromise(); this.triggerGamification(100); this.chatHistory.push({role:'assistant', text:`🍅 Sesión de ${this.minutes}min completada.`}); this.enviarMensaje(true); alert("¡Bien hecho! Descansa."); this.resetTimer(5); } catch(e){} } else { alert("A trabajar!"); this.resetTimer(this.getPreferredFocusTime()); } }

  async openProjectsModal() { this.showProjectsModal = true; this.activeProject = null; this.loadProjects(); }
  closeProjectsModal() { this.showProjectsModal = false; }
  async loadProjects() { try { const d: any = await this.http.get(`${this.apiUrl}/proyectos`).toPromise(); this.projectsList = d||[]; } catch(e){} }
  async createProject() { if(!this.newProjectData.nombre) return; this.isUpdating=true; try { await this.http.post(`${this.apiUrl}/crear_proyecto`, this.newProjectData).toPromise(); this.loadProjects(); this.newProjectData={nombre:'', descripcion:'', fecha_fin:''}; } catch(e){} finally { this.isUpdating=false; } }
  selectProject(p: Project) { this.activeProject = p; }
  async toggleMilestone(m: Milestone) { if(!this.activeProject) return; try { await this.http.post(`${this.apiUrl}/actualizar_hitos`, {project_id:this.activeProject.id, hitos:this.activeProject.hitos}).toPromise(); const t=this.activeProject.hitos.length; const c=this.activeProject.hitos.filter(h=>h.completado).length; this.activeProject.progreso=Math.floor((c/t)*100); if(m.completado) this.triggerGamification(200); } catch(e){} }
  async deleteProject(id: string) { if(confirm("¿Borrar?")) { await this.http.post(`${this.apiUrl}/eliminar_proyecto`, {id}).toPromise(); this.activeProject=null; this.loadProjects(); } }

  async openEditModal() { await this.loadProfileForEdit(true); this.showEditModal=true; }
  closeEditModal() { this.showEditModal=false; }
  async loadProfileForEdit(u: boolean) { try { const d:any = await this.http.get(`${this.apiUrl}/obtener_perfil`).toPromise(); if(d) { if(u) this.editData={...d}; this.profileData={...d}; } } catch(e){} }
  async updateProfile() { try { await this.http.post(`${this.apiUrl}/actualizar_perfil`, this.editData).toPromise(); this.profileData={...this.editData}; this.showEditModal=false; } catch(e){} }

  async cargarMaterias() { try { const m:any = await this.http.get(`${this.apiUrl}/materias`).toPromise(); this.listaMateriasSugeridas = m||[]; } catch(e){ this.listaMateriasSugeridas=[]; } }
  triggerGamification(xp: number) { this.xpGanado = xp; this.showXpAnim = true; this.lanzarConfeti(); setTimeout(() => this.showXpAnim = false, 3000); }
  lanzarConfeti() { const c = ['#f39c12', '#e74c3c', '#9b59b6', '#2ecc71', '#3498db']; for (let i = 0; i < 40; i++) { const p = document.createElement('div'); p.className = 'confeti-particle'; p.style.left = Math.random() * 100 + 'vw'; p.style.backgroundColor = c[Math.floor(Math.random() * c.length)]; p.style.animationDuration = (Math.random() * 2 + 2) + 's'; p.style.opacity = Math.random().toString(); document.body.appendChild(p); setTimeout(() => { p.remove(); }, 3000); } }
  getPriorityClass(p: string) { return p === 'Alta' ? 'priority-alta' : 'priority-media'; }
  getTypeClass(type: string): string { if (!type) return 'estudio'; let safe = type.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase(); if (safe.includes(' ')) safe = safe.split(' ')[0]; return safe; }
}
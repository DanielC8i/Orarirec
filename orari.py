# Programma per la generazione automatica dei turni in una struttura ricettiva 24/7 con interfaccia grafica e gestione ferie/recuperi

import random
import datetime
import pandas as pd
from fpdf import FPDF
import tkinter as tk
from tkinter import messagebox, simpledialog, filedialog
import calendar
import pickle
import os

# Costanti dei turni
TURNI = {
    'M2': ("07:00", "12:40"),
    'P2': ("12:30", "18:10"),
    'S': ("18:00", "23:00"),
    'P': ("15:30", "23:00"),
    'M': ("08:00", "15:00"),
    'N': ("23:00", "07:00"),
    'C': ("08:00", "15:00"),
    'C_sabato': ("11:30", "18:30"),
    'bar': ("15:30", "22:00"),
    'bar_matin': ("16:00", "21:00")
}

# Classe Dipendente con supporto per ferie e recuperi
class Dipendente:
    def __init__(self, nome):
        self.nome = nome
        self.turni = []
        self.ferie = []
        self.riposi_aggiuntivi = []
        self.recuperi = []
        self.turni_possibili = list(TURNI.keys())  # Tutti i turni disponibili di default
        self.priorita_turni = {k: 1 for k in TURNI.keys()}  # Priorità default 1 per ogni turno

    def aggiungi_turno(self, giorno, tipo_turno):
        self.turni.append((giorno, tipo_turno))

    def modifica_turno(self, giorno, nuovo_turno):
        self.turni = [(g, t) if g != giorno else (g, nuovo_turno) for g, t in self.turni]

    def assegna_ferie(self, inizio, fine):
        self.ferie.append((inizio, fine))

    def assegna_riposo_aggiuntivo(self, giorno):
        self.riposi_aggiuntivi.append(giorno)

    def assegna_recupero(self, giorno):
        self.recuperi.append(giorno)

    def giorni_lavorati_consecutivi(self, giorno):
        date_lavorate = sorted([t[0] for t in self.turni])
        count = 0
        for i in range(len(date_lavorate) - 1, -1, -1):
            if date_lavorate[i] < giorno:
                if (giorno - date_lavorate[i]).days == count + 1:
                    count += 1
                else:
                    break
        return count

    def ore_totali(self):
        ore = 0
        for _, turno in self.turni:
            inizio, fine = TURNI[turno]
            fmt = "%H:%M"
            tdelta = datetime.datetime.strptime(fine, fmt) - datetime.datetime.strptime(inizio, fmt)
            ore += tdelta.seconds / 3600
        return ore

    def azzera_turni(self):
        self.turni = []

# Funzioni principali

def genera_turni(mese, anno, dipendenti):
    num_giorni = calendar.monthrange(anno, mese)[1]
    giorni_mese = [datetime.date(anno, mese, giorno) for giorno in range(1, num_giorni + 1)]
    calendario = {}

    # Per ogni dipendente, tiene traccia dell'ultimo giorno di riposo
    ultimi_riposi = {d.nome: None for d in dipendenti}
    # Tiene traccia se il dipendente era a riposo il giorno prima
    riposo_ieri = {d.nome: False for d in dipendenti}

    for giorno in giorni_mese:
        calendario[giorno] = {}
        random.shuffle(dipendenti)
        assegnati = []

        # Usa più spesso la forma con più personale
        if random.random() < 0.8:
            turni_giornalieri = ['M2', 'P2', 'S', 'P']
        else:
            turni_giornalieri = ['M', 'P', 'P']

        for tipo_turno in turni_giornalieri:
            for dip in dipendenti:
                # Calcola giorni dall'ultimo riposo
                ultimo_riposo = ultimi_riposi[dip.nome]
                giorni_dal_riposo = (giorno - ultimo_riposo).days if ultimo_riposo else 7
                # Un solo riposo ogni 6/7 giorni
                if giorni_dal_riposo < 6:
                    continue
                # Non permettere due riposi consecutivi
                if riposo_ieri[dip.nome]:
                    continue
                if giorno in dip.recuperi or any(start <= giorno <= end for (start, end) in dip.ferie):
                    continue
                if dip not in assegnati and tipo_turno in dip.turni_possibili:
                    calendario[giorno][dip.nome] = tipo_turno
                    dip.aggiungi_turno(giorno, tipo_turno)
                    assegnati.append(dip)
                    break
        # Se la giornata non è coperta, aggiungi qualcuno in M o P
        if len(calendario[giorno]) < len(turni_giornalieri):
            for tipo_turno in ['M', 'P']:
                for dip in dipendenti:
                    if dip not in assegnati and tipo_turno in dip.turni_possibili and not riposo_ieri[dip.nome]:
                        calendario[giorno][dip.nome] = tipo_turno
                        dip.aggiungi_turno(giorno, tipo_turno)
                        assegnati.append(dip)
                        if len(calendario[giorno]) >= len(turni_giornalieri):
                            break
                if len(calendario[giorno]) >= len(turni_giornalieri):
                    break
        # Aggiorna ultimo riposo e flag riposo_ieri
        for dip in dipendenti:
            if dip.nome not in calendario[giorno]:
                # Se era già a riposo ieri, forziamo che oggi lavori (non lasciamo due riposi consecutivi)
                if riposo_ieri[dip.nome]:
                    # Forza un turno qualsiasi disponibile
                    for tipo_turno in dip.turni_possibili:
                        if dip.nome not in calendario[giorno]:
                            calendario[giorno][dip.nome] = tipo_turno
                            dip.aggiungi_turno(giorno, tipo_turno)
                            break
                    riposo_ieri[dip.nome] = False
                else:
                    ultimi_riposi[dip.nome] = giorno
                    riposo_ieri[dip.nome] = True
            else:
                riposo_ieri[dip.nome] = False
    return calendario

# Funzione per esportare in PDF con colori
class PDF(FPDF):
    def header(self):
        self.set_font("Arial", "B", 12)
        self.cell(0, 10, "Turni Mensili", ln=True, align="C")

    def create_table(self, calendario, dipendenti):
        self.set_font("Arial", size=10)
        self.add_page()
        giorni = list(calendario.keys())
        header = ["Giorno"] + [d.nome for d in dipendenti]
        self.set_fill_color(200, 220, 255)
        self.cell(25, 10, "Giorno", 1, 0, "C", True)
        for nome in header[1:]:
            self.cell(25, 10, nome, 1, 0, "C", True)
        self.ln()

        for giorno in giorni:
            self.cell(25, 10, giorno.strftime("%d/%m"), 1)
            for d in dipendenti:
                turno = calendario[giorno].get(d.nome, "")
                colore = None
                if any(start <= giorno <= end for (start, end) in d.ferie):
                    colore = (144, 238, 144)
                    turno = "FERIE"
                elif giorno in d.recuperi:
                    colore = (255, 255, 153)
                    turno = "RECUP"
                if colore:
                    self.set_fill_color(*colore)
                    self.cell(25, 10, turno, 1, 0, "C", True)
                    self.set_fill_color(255, 255, 255)
                else:
                    self.cell(25, 10, turno, 1)
            self.ln()

# Funzione per esportare in PDF con layout stile orarirec
class PDFStileOrarirec(FPDF):
    def header(self):
        self.set_font("Arial", "B", 10)
        self.cell(0, 8, "Turni Mensili - Stile Orarirec", ln=True, align="C")

    def create_table(self, calendario, dipendenti):
        self.set_font("Arial", size=8)
        self.add_page(orientation="L")

        giorni = list(calendario.keys())
        giorni.sort()
        nomi_dipendenti = [d.nome for d in dipendenti]

        # Giorni della settimana (sopra ai numeri)
        self.cell(30, 8, "", 1, 0, "C")
        for giorno in giorni:
            nome_giorno = calendar.day_abbr[giorno.weekday()][:3]
            self.cell(10, 8, nome_giorno, 1, 0, "C")
        self.ln()

        # Numeri dei giorni
        self.cell(30, 8, "", 1, 0, "C")
        for giorno in giorni:
            self.cell(10, 8, str(giorno.day), 1, 0, "C")
        self.ln()

        # Riga per ogni dipendente
        for d in dipendenti:
            self.cell(30, 8, d.nome, 1, 0, "L")
            for giorno in giorni:
                turno = calendario.get(giorno, {}).get(d.nome, "")
                colore = None
                if any(start <= giorno <= end for (start, end) in d.ferie):
                    colore = (144, 238, 144)
                    turno = "FER"
                elif giorno in d.recuperi:
                    colore = (255, 255, 153)
                    turno = "REC"

                if colore:
                    self.set_fill_color(*colore)
                    self.cell(10, 8, turno, 1, 0, "C", True)
                    self.set_fill_color(255, 255, 255)
                else:
                    self.cell(10, 8, turno, 1, 0, "C")
            self.ln()

        # Riga finale: ore totali
        self.cell(30, 8, "Ore Totali", 1, 0, "R")
        for d in dipendenti:
            self.cell(10, 8, f"{int(d.ore_totali())}", 1, 0, "C")
        self.ln()

# Interfaccia grafica
class TurniApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Gestione Turni Struttura Ricettiva")
        self.dipendenti = self.carica_dipendenti()
        self.calendario = {}
        self.anteprima_calendario = None

        self.label = tk.Label(root, text="Gestione Dipendenti:")
        self.label.pack()

        self.lista_box = tk.Listbox(root, selectmode=tk.SINGLE, width=50)
        self.lista_box.pack()
        self.lista_box.bind('<<ListboxSelect>>', self.mostra_preferenze_turni)

        self.entry = tk.Entry(root)
        self.entry.pack()

        self.aggiungi_button = tk.Button(root, text="Aggiungi Dipendente", command=self.aggiungi_dipendente)
        self.aggiungi_button.pack()

        self.rimuovi_button = tk.Button(root, text="Rimuovi Dipendente", command=self.rimuovi_dipendente)
        self.rimuovi_button.pack()

        self.preferenze_frame = tk.Frame(root)
        self.preferenze_frame.pack()
        self.preferenze_label = tk.Label(self.preferenze_frame, text="Preferenze turni (seleziona un dipendente)")
        self.preferenze_label.pack()
        self.turni_vars = {}
        self.priorita_vars = {}

        self.aggiorna_preferenze_turni()

        self.ferie_button = tk.Button(root, text="Assegna Ferie", command=self.assegna_ferie)
        self.ferie_button.pack()

        self.recupero_button = tk.Button(root, text="Assegna Recupero", command=self.assegna_recupero)
        self.recupero_button.pack()

        self.modifica_tabella_button = tk.Button(root, text="Modifica Tabella Manualmente", command=self.modifica_tabella)
        self.modifica_tabella_button.pack()

        self.genera_button = tk.Button(root, text="Genera Turni (Anteprima)", command=self.genera_turni_anteprima)
        self.genera_button.pack()

    def salva_dipendenti(self):
        with open("dipendenti.pkl", "wb") as f:
            pickle.dump(self.dipendenti, f)

    def carica_dipendenti(self):
        if os.path.exists("dipendenti.pkl"):
            with open("dipendenti.pkl", "rb") as f:
                return pickle.load(f)
        return []

    def aggiorna_lista(self):
        self.lista_box.delete(0, tk.END)
        for dip in self.dipendenti:
            self.lista_box.insert(tk.END, dip.nome)
        self.salva_dipendenti()

    def aggiungi_dipendente(self):
        nome = self.entry.get().strip()
        if nome and nome not in [d.nome for d in self.dipendenti]:
            self.dipendenti.append(Dipendente(nome))
            self.entry.delete(0, tk.END)
            self.aggiorna_lista()
        else:
            messagebox.showerror("Errore", "Nome invalido o già presente.")

    def rimuovi_dipendente(self):
        selezione = self.lista_box.curselection()
        if selezione:
            index = selezione[0]
            self.dipendenti.pop(index)
            self.aggiorna_lista()
        else:
            messagebox.showerror("Errore", "Seleziona un dipendente da rimuovere.")

    def assegna_ferie(self):
        nome = simpledialog.askstring("Assegna Ferie", "Nome del dipendente:")
        inizio_str = simpledialog.askstring("Inizio Ferie", "Data inizio (YYYY-MM-DD):")
        fine_str = simpledialog.askstring("Fine Ferie", "Data fine (YYYY-MM-DD):")
        try:
            inizio = datetime.datetime.strptime(inizio_str, "%Y-%m-%d").date()
            fine = datetime.datetime.strptime(fine_str, "%Y-%m-%d").date()
            dip = next((d for d in self.dipendenti if d.nome == nome), None)
            if dip:
                dip.assegna_ferie(inizio, fine)
                messagebox.showinfo("Successo", "Ferie assegnate.")
            else:
                messagebox.showerror("Errore", "Dipendente non trovato.")
        except Exception as e:
            messagebox.showerror("Errore", f"Errore nell'assegnazione: {e}")

    def assegna_recupero(self):
        nome = simpledialog.askstring("Assegna Recupero", "Nome del dipendente:")
        giorno_str = simpledialog.askstring("Recupero", "Data del recupero (YYYY-MM-DD):")
        try:
            giorno = datetime.datetime.strptime(giorno_str, "%Y-%m-%d").date()
            dip = next((d for d in self.dipendenti if d.nome == nome), None)
            if dip:
                dip.assegna_recupero(giorno)
                messagebox.showinfo("Successo", "Recupero assegnato.")
            else:
                messagebox.showerror("Errore", "Dipendente non trovato.")
        except Exception as e:
            messagebox.showerror("Errore", f"Errore nell'assegnazione: {e}")

    def modifica_turno(self):
        nome = simpledialog.askstring("Modifica Turno", "Nome del dipendente:")
        giorno_str = simpledialog.askstring("Modifica Turno", "Giorno (YYYY-MM-DD):")
        nuovo_turno = simpledialog.askstring("Modifica Turno", f"Nuovo turno ({'/'.join(TURNI.keys())}):")
        try:
            giorno = datetime.datetime.strptime(giorno_str, "%Y-%m-%d").date()
            dip = next((d for d in self.dipendenti if d.nome == nome), None)
            if dip and nuovo_turno in TURNI:
                dip.modifica_turno(giorno, nuovo_turno)
                if giorno in self.calendario:
                    self.calendario[giorno][nome] = nuovo_turno
                messagebox.showinfo("Successo", "Turno modificato correttamente.")
            else:
                messagebox.showerror("Errore", "Dati non validi.")
        except Exception as e:
            messagebox.showerror("Errore", f"Errore nella modifica: {e}")

    def genera_turni_gui(self):
        try:
            if not self.dipendenti:
                messagebox.showerror("Errore", "Aggiungi almeno un dipendente.")
                return
            # Azzera i turni di tutti i dipendenti prima di generare
            for dip in self.dipendenti:
                dip.azzera_turni()
            messagebox.showinfo("Info", "Generazione turni in corso...")
            self.calendario = genera_turni(6, 2025, self.dipendenti)
            pdf = PDFStileOrarirec()
            pdf.create_table(self.calendario, self.dipendenti)
            save_path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF files", "*.pdf")])
            if save_path:
                pdf.output(save_path)
                messagebox.showinfo("Successo", f"Turni salvati in {save_path}")
            else:
                messagebox.showwarning("Attenzione", "Salvataggio annullato. Il file PDF non è stato creato.")
        except Exception as e:
            messagebox.showerror("Errore", f"Errore durante la generazione dei turni: {e}")

    def mostra_preferenze_turni(self, event=None):
        for widget in self.preferenze_frame.winfo_children():
            if widget != self.preferenze_label:
                widget.destroy()
        selezione = self.lista_box.curselection()
        if not selezione:
            return
        index = selezione[0]
        dip = self.dipendenti[index]
        self.turni_vars = {}
        self.priorita_vars = {}
        for turno in TURNI.keys():
            var = tk.BooleanVar(value=turno in dip.turni_possibili)
            prio = tk.IntVar(value=dip.priorita_turni.get(turno, 1))
            self.turni_vars[turno] = var
            self.priorita_vars[turno] = prio
            frame = tk.Frame(self.preferenze_frame)
            frame.pack(anchor='w')
            tk.Checkbutton(frame, text=turno, variable=var).pack(side='left')
            tk.Label(frame, text='Priorità:').pack(side='left')
            tk.Spinbox(frame, from_=1, to=5, width=2, textvariable=prio).pack(side='left')
        tk.Button(self.preferenze_frame, text="Salva Preferenze", command=self.salva_preferenze_turni).pack()

    def salva_preferenze_turni(self):
        selezione = self.lista_box.curselection()
        if not selezione:
            return
        index = selezione[0]
        dip = self.dipendenti[index]
        dip.turni_possibili = [t for t, v in self.turni_vars.items() if v.get()]
        dip.priorita_turni = {t: self.priorita_vars[t].get() for t in dip.turni_possibili}
        self.salva_dipendenti()
        messagebox.showinfo("Successo", "Preferenze turni salvate!")

    def aggiorna_preferenze_turni(self):
        self.mostra_preferenze_turni()

    def modifica_tabella(self):
        # Da implementare: apertura finestra con tabella modificabile
        messagebox.showinfo("Info", "Funzionalità di modifica tabella manuale in sviluppo.")

    def genera_turni_anteprima(self):
        try:
            if not self.dipendenti:
                messagebox.showerror("Errore", "Aggiungi almeno un dipendente.")
                return
            for dip in self.dipendenti:
                dip.azzera_turni()
            self.anteprima_calendario = genera_turni(6, 2025, self.dipendenti)
            self.mostra_anteprima_tabella()
        except Exception as e:
            messagebox.showerror("Errore", f"Errore durante la generazione dei turni: {e}")

    def mostra_anteprima_tabella(self):
        if not self.anteprima_calendario:
            messagebox.showerror("Errore", "Nessuna anteprima disponibile.")
            return
        anteprima = tk.Toplevel(self.root)
        anteprima.title("Anteprima e Modifica Tabella Turni")
        giorni = sorted(self.anteprima_calendario.keys())
        dipendenti = self.dipendenti
        turni_possibili = {d.nome: d.turni_possibili for d in dipendenti}
        celle_vars = {}

        # Intestazione giorni
        tk.Label(anteprima, text="Dipendente").grid(row=0, column=0, sticky="nsew")
        for col, giorno in enumerate(giorni, 1):
            tk.Label(anteprima, text=giorno.strftime("%d/%m")).grid(row=0, column=col, sticky="nsew")

        # Celle modificabili
        for r, d in enumerate(dipendenti, 1):
            tk.Label(anteprima, text=d.nome).grid(row=r, column=0, sticky="nsew")
            celle_vars[d.nome] = {}
            for c, giorno in enumerate(giorni, 1):
                turno_attuale = self.anteprima_calendario.get(giorno, {}).get(d.nome, "")
                var = tk.StringVar(value=turno_attuale)
                opzioni = [""] + turni_possibili[d.nome]
                om = tk.OptionMenu(anteprima, var, *opzioni)
                om.grid(row=r, column=c, sticky="nsew")
                celle_vars[d.nome][giorno] = var

        def salva_modifiche():
            for d in dipendenti:
                for giorno in giorni:
                    val = celle_vars[d.nome][giorno].get()
                    if val:
                        self.anteprima_calendario[giorno][d.nome] = val
                    elif d.nome in self.anteprima_calendario[giorno]:
                        del self.anteprima_calendario[giorno][d.nome]
            anteprima.destroy()
            self.chiedi_salva_pdf()

        def annulla():
            anteprima.destroy()

        tk.Button(anteprima, text="Salva e Genera PDF", command=salva_modifiche).grid(row=len(dipendenti)+1, column=0, columnspan=2)
        tk.Button(anteprima, text="Annulla", command=annulla).grid(row=len(dipendenti)+1, column=2, columnspan=2)

    def chiedi_salva_pdf(self):
        if messagebox.askyesno("Salva PDF", "Vuoi salvare il PDF dei turni?"):
            pdf = PDFStileOrarirec()
            pdf.create_table(self.anteprima_calendario, self.dipendenti)
            save_path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF files", "*.pdf")])
            if save_path:
                pdf.output(save_path)
                messagebox.showinfo("Successo", f"Turni salvati in {save_path}")
            else:
                messagebox.showwarning("Attenzione", "Salvataggio annullato. Il file PDF non è stato creato.")
        else:
            messagebox.showinfo("Info", "Modifica la tabella e salva quando sei pronto.")

if __name__ == "__main__":
    root = tk.Tk()
    app = TurniApp(root)
    root.mainloop()

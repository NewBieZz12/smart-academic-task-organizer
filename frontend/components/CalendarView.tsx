'use client';
import React, { useState } from 'react';

// 🌟 Production-ready explicit Assignment tracking type structure
export interface Assignment {
  project_id?: string;
  course_code: string;     
  course_name: string;     
  assessment_title: string;
  deadline_iso: string;    
  priority: string;        
  sorting_score: number;   
}

interface CalendarViewProps {
  projectId?: string;
  assignments: Assignment[]; // State-synced tracking array passed downstream from page.tsx
  onDeleteAssignment?: (assignment: Assignment) => void; // 🔥 Callback handler to notify parent container
}

const normalizeProjectId = (projectId?: string) => {
  const cleaned = String(projectId || '').trim();
  return cleaned.length > 0 ? cleaned : 'project-1';
};

export default function CalendarView({
  projectId = 'project-1',
  assignments = [],
  onDeleteAssignment
}: CalendarViewProps) {
  // Initializing calendar view window safely inside the current tracking frame (June 2026)
  const [currentDate, setCurrentDate] = useState<Date>(new Date(2026, 5, 1));
  const [selectedAssignment, setSelectedAssignment] = useState<Assignment | null>(null);

  const activeProjectId = normalizeProjectId(projectId);

  const scopedAssignments = assignments.filter((assignment) => {
    if (!assignment.project_id) return true;
    return normalizeProjectId(assignment.project_id) === activeProjectId;
  });

  const currentYear = currentDate.getFullYear();
  const currentMonthIdx = currentDate.getMonth();

  const weekdays = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  const monthNames = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
  ];

  const handlePrevMonth = () => {
    setCurrentDate(new Date(currentYear, currentMonthIdx - 1, 1));
  };

  const handleNextMonth = () => {
    setCurrentDate(new Date(currentYear, currentMonthIdx + 1, 1));
  };

  // Month Grid Dimensional Structural Calculations
  const firstDayOfWeekIndex = new Date(currentYear, currentMonthIdx, 1).getDay();
  const totalDaysInActiveMonth = new Date(currentYear, currentMonthIdx + 1, 0).getDate();
  const totalDaysInPrevMonth = new Date(currentYear, currentMonthIdx, 0).getDate();

  const daysInMonth = Array.from({ length: totalDaysInActiveMonth }, (_, i) => i + 1);

  const prevMonthPaddingDays = Array.from({ length: firstDayOfWeekIndex }, (_, i) => {
    return totalDaysInPrevMonth - firstDayOfWeekIndex + i + 1;
  });

  const totalGridCellsUsed = prevMonthPaddingDays.length + daysInMonth.length;
  const trailingPaddingCellsCount = 42 - totalGridCellsUsed;
  const nextMonthTrailingDays = Array.from({ length: trailingPaddingCellsCount }, (_, i) => i + 1);

  // Core Academic Engineering Subject Theme Classifier
  const getCourseBadgeColor = (codeStr: string = '', priority: string = '') => {
    if (priority?.toLowerCase() === 'urgent' || priority?.toLowerCase() === 'high' || priority?.toLowerCase() === 'critical') {
      return 'bg-rose-50 text-rose-700 border-rose-200 hover:bg-rose-100/70';
    }
    const cleanCode = codeStr.toUpperCase();
    if (cleanCode.includes('SWE305')) return 'bg-indigo-50 text-indigo-700 border-indigo-100 hover:bg-indigo-100/70';
    if (cleanCode.includes('SWE403')) return 'bg-blue-50 text-blue-700 border-blue-100 hover:bg-blue-100/70';
    if (cleanCode.includes('SWE401')) return 'bg-purple-50 text-purple-700 border-purple-100 hover:bg-purple-100/70';
    if (cleanCode.includes('SWE404')) return 'bg-amber-50 text-amber-700 border-amber-100 hover:bg-amber-100/70';
    if (cleanCode.includes('SWE405')) return 'bg-sky-50 text-sky-700 border-sky-100 hover:bg-sky-100/70';
    if (cleanCode.includes('SWE407')) return 'bg-emerald-50 text-emerald-700 border-emerald-100 hover:bg-emerald-100/70';
    if (cleanCode.includes('G0145') || cleanCode.includes('GO145')) return 'bg-teal-50 text-teal-700 border-teal-100 hover:bg-teal-100/70';
    if (cleanCode.includes('G0174')) return 'bg-orange-50 text-orange-700 border-orange-100 hover:bg-orange-100/70';

    return 'bg-slate-50 text-slate-700 border-slate-100 hover:bg-slate-100/70';
  };

  // 🔥 Explicit structural deletion handler
  const handleDeleteTrigger = (targetTarget: Assignment) => {
    if (onDeleteAssignment) {
      onDeleteAssignment(targetTarget);
    }
    setSelectedAssignment(null); // Clear active modal window viewport safely
  };

  return (
    <div className="w-full h-full bg-white rounded-2xl shadow-sm border border-slate-200 flex flex-col overflow-hidden animate-fade-in relative">
      
      {/* Calendar Header Control Block */}
      <div className="p-4 border-b border-slate-100 bg-slate-50/50 flex justify-between items-center shrink-0">
        <div>
          <h3 className="font-bold text-slate-800 text-sm">Calendar</h3>
          <p className="text-[10px] text-slate-400 font-semibold mt-0.5">
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handlePrevMonth}
            className="p-1 px-2 hover:bg-slate-200 active:bg-slate-300 rounded text-xs font-bold text-slate-600 transition-colors select-none"
          >
            ◀
          </button>
          <span className="text-xs font-bold text-slate-700 min-w-[100px] text-center uppercase tracking-wider">
            {monthNames[currentMonthIdx]} {currentYear}
          </span>
          <button
            onClick={handleNextMonth}
            className="p-1 px-2 hover:bg-slate-200 active:bg-slate-300 rounded text-xs font-bold text-slate-600 transition-colors select-none"
          >
            ▶
          </button>
        </div>
      </div>

      {/* Grid Canvas Mesh */}
      <div className="flex-1 p-4 overflow-y-auto bg-white flex flex-col">
        <div className="grid grid-cols-7 gap-1 text-center mb-1 shrink-0">
          {weekdays.map(d => (
            <div key={d} className="text-[11px] font-bold text-slate-400 uppercase tracking-wider py-1">{d}</div>
          ))}
        </div>

        <div className="grid grid-cols-7 gap-1 flex-1 min-h-[400px]">
          {/* Historical Offset Padding */}
          {prevMonthPaddingDays.map((prevDay) => (
            <div key={`prev-${prevDay}`} className="bg-slate-50/40 rounded-xl p-1.5 border border-slate-100/70 opacity-40 text-xs font-bold text-slate-400 select-none min-h-[85px]">
              {prevDay}
            </div>
          ))}

          {/* Active Month Core Cells */}
          {daysInMonth.map((day) => {
            const targetYearStr = String(currentYear);
            const targetMonthStr = String(currentMonthIdx + 1).padStart(2, '0');
            const targetDayStr = String(day).padStart(2, '0');
            const calculatedGridIsoDate = `${targetYearStr}-${targetMonthStr}-${targetDayStr}`;

            const dayEvents = scopedAssignments.filter(assign => assign.deadline_iso && assign.deadline_iso.startsWith(calculatedGridIsoDate));

            return (
              <div key={`active-${day}`} className="bg-white hover:bg-slate-50/80 transition-colors border border-slate-100 rounded-xl p-1.5 flex flex-col justify-between group min-h-[85px]">
                <span className="text-xs font-bold text-slate-400 group-hover:text-slate-700 transition-colors">{day}</span>

                <div className="space-y-1 mt-1 flex-1 overflow-y-auto max-h-[65px] custom-scrollbar">
                  {dayEvents.map((event, index) => {
                    const styleThemeClasses = getCourseBadgeColor(event.course_code, event.priority);

                    return (
                      <div
                        key={index}
                        onClick={() => setSelectedAssignment(event)}
                        className={`text-[9px] p-1 rounded font-bold border tracking-wide shadow-2xs leading-tight cursor-pointer transition-all duration-150 active:scale-[0.97] ${styleThemeClasses} truncate`}
                        title="Click to view detailed assessment profile"
                      >
                        <span className="opacity-90 block text-[7.5px] uppercase font-extrabold tracking-wider">{event.course_code}</span>
                        <span className="text-slate-800 block truncate">{event.assessment_title}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}

          {/* Trailing Future Offset Padding */}
          {nextMonthTrailingDays.map((nextDay) => (
            <div key={`next-${nextDay}`} className="bg-slate-50/40 rounded-xl p-1.5 border border-slate-100/70 opacity-40 text-xs font-bold text-slate-400 select-none min-h-[85px]">
              {nextDay}
            </div>
          ))}
        </div>
      </div>

      {/* ========================================================== */}
      {/* STRUCTURED INTERACTIVE DATA ASSIGNMENT SHEET MODAL         */}
      {/* ========================================================== */}
      {selectedAssignment && (
        <div className="absolute inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4 z-50 animate-fade-in">
          <div className="bg-white rounded-2xl w-full max-w-md border border-slate-100 shadow-xl overflow-hidden p-5 flex flex-col gap-4 transform transition-all animate-scale-up">
          
            {/* Modal Header */}
            <div className="flex items-start justify-between border-b border-slate-100 pb-3">
              <div>
                <span className="text-[9px] font-extrabold px-2.5 py-0.5 rounded-full bg-blue-50 text-blue-700 uppercase tracking-wider border border-blue-200">
                  {selectedAssignment.course_code || 'Academic'} Profile
                </span>
                <h4 className="font-bold text-slate-800 text-base mt-2 leading-snug">
                  {selectedAssignment.assessment_title}
                </h4>
              </div>
              <button
                onClick={() => setSelectedAssignment(null)}
                className="text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg p-1 px-2 text-sm transition-colors font-bold"
              >
                ✕
              </button>
            </div>

            {/* Metric Property Array Block */}
            <div className="space-y-3.5 py-1">
              <div>
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block mb-1">Course Code</span>
                <p className="text-xs font-bold text-blue-800 bg-blue-50/50 p-2 rounded-lg border border-blue-100 max-w-max px-3">
                  {selectedAssignment.course_code}
                </p>
              </div>

              <div>
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block mb-1">Course Name</span>
                <p className="text-xs font-semibold text-slate-700 bg-slate-50 p-2.5 rounded-lg border border-slate-200/60">
                  {selectedAssignment.course_name}
                </p>
              </div>

              <div>
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block mb-1">Assessment Title</span>
                <p className="text-xs font-medium text-slate-700 bg-slate-50 p-2.5 rounded-lg border border-slate-200/60 font-mono">
                  {selectedAssignment.assessment_title}
                </p>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block mb-1">Submission Date</span>
                  <p className="text-xs font-semibold text-slate-700 bg-slate-50 p-2.5 rounded-lg border border-slate-200/50 flex items-center gap-1.5">
                     {selectedAssignment.deadline_iso ? selectedAssignment.deadline_iso.split('T')[0] : 'No Target Configured'}
                  </p>
                </div>
              </div>
            </div>

            {/* 🔥 Footer Control Tray with Clear Log Functionality */}
            <div className="pt-3 border-t border-slate-100 flex justify-between items-center">
              <button
                onClick={() => handleDeleteTrigger(selectedAssignment)}
                className="px-4 py-1.5 bg-rose-50 border border-rose-200 hover:bg-rose-100 active:scale-95 text-rose-700 text-xs font-bold rounded-xl transition-all flex items-center gap-1.5"
                title="Permanently erase this milestone log from your calendar workspace"
              >
                 Clear Log
              </button>
             
              <button
                onClick={() => setSelectedAssignment(null)}
                className="px-5 py-1.5 bg-slate-800 hover:bg-slate-900 active:scale-95 text-white text-xs font-bold rounded-xl transition-all shadow-sm"
              >
                Dismiss
              </button>
            </div>

          </div>
        </div>
      )}

    </div>
  );
}
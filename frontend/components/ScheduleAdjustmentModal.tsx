interface ModalProps {
    isOpen: boolean;
    onClose: () => void;
    data: any;
    setData: (data: any) => void;
    onFinalSave: () => void;
  }
  
  export default function ScheduleAdjustmentModal({ isOpen, onClose, data, setData, onFinalSave }: ModalProps) {
    if (!isOpen) return null;
  
    return (
      <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center backdrop-blur-sm">
        <div className="bg-white dark:bg-slate-900 p-6 rounded-xl shadow-2xl max-w-md w-full border border-slate-200 dark:border-slate-800">
          <h3 className="text-lg font-bold text-slate-900 dark:text-white mb-2">🤖 Genetic Algorithm Optimizer</h3>
          <p className="text-xs text-slate-500 mb-4">The GA engine calculated the following optimal slot based on your current workload. Adjust below if necessary:</p>
          
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-semibold mb-1 text-slate-700 dark:text-slate-300">Target Date</label>
              <input 
                type="date" 
                className="w-full p-2 border rounded-lg text-sm dark:bg-slate-800"
                value={data.suggested_date}
                onChange={(e) => setData({ ...data, suggested_date: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-xs font-semibold mb-1 text-slate-700 dark:text-slate-300">Target Time Slot</label>
              <input 
                type="time" 
                className="w-full p-2 border rounded-lg text-sm dark:bg-slate-800"
                value={data.suggested_time}
                onChange={(e) => setData({ ...data, suggested_time: e.target.value })}
              />
            </div>
          </div>
  
          <div className="flex justify-end gap-2 mt-6">
            <button onClick={onClose} className="px-4 py-2 text-xs border rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800">Cancel</button>
            <button onClick={onFinalSave} className="px-4 py-2 text-xs bg-indigo-600 text-white rounded-lg hover:bg-indigo-700">Confirm & Commit</button>
          </div>
        </div>
      </div>
    );
  }
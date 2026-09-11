import { Shield, Lock, Key, Users } from 'lucide-react';

export default function SecurityPosture() {
  const score = 94;
  
  return (
    <div className="bg-slate-900/50 border border-slate-700/50 rounded-2xl overflow-hidden shadow-xl shadow-black/20 animate-in fade-in slide-in-from-bottom-4 duration-500">
      
      <div className="px-6 py-5 border-b border-slate-700/50 bg-slate-900/80 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-emerald-500/10 rounded-lg">
            <Shield className="w-5 h-5 text-emerald-400" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-slate-200">Security Posture</h3>
            <p className="text-xs text-slate-400 mt-0.5">Database configuration & access controls</p>
          </div>
        </div>
      </div>

      <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-8">
        
        {/* Overall Score */}
        <div className="flex flex-col items-center justify-center border-r border-slate-800/60 pr-8">
          <div className="relative flex items-center justify-center w-40 h-40">
            <svg className="w-full h-full transform -rotate-90" viewBox="0 0 36 36">
              <path
                className="text-slate-800"
                strokeWidth="3"
                stroke="currentColor"
                fill="none"
                d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
              />
              <path
                className="text-emerald-500 transition-all duration-1000 ease-out"
                strokeWidth="3"
                strokeDasharray={`${score}, 100`}
                strokeLinecap="round"
                stroke="currentColor"
                fill="none"
                d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
              />
            </svg>
            <div className="absolute flex flex-col items-center justify-center">
              <span className="text-4xl font-black text-slate-100">{score}</span>
              <span className="text-[10px] uppercase font-bold text-slate-500 tracking-widest mt-1">Grade A</span>
            </div>
          </div>
          <p className="text-sm text-slate-400 text-center mt-4">
            Security baseline meets strict compliance standards for immutable audit trails.
          </p>
        </div>

        {/* Configuration Checklist */}
        <div className="flex flex-col justify-center space-y-5">
          <div className="flex items-start space-x-3">
            <div className="mt-0.5 w-6 h-6 rounded bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center flex-shrink-0">
              <Lock className="w-3.5 h-3.5 text-emerald-400" />
            </div>
            <div>
              <p className="text-sm font-semibold text-slate-200">Role Segregation</p>
              <p className="text-xs text-slate-400 mt-0.5">PostgreSQL roles strictly isolated. App user cannot mutate <code className="text-violet-300 bg-violet-500/10 px-1 py-0.5 rounded">audit_log</code> directly.</p>
            </div>
          </div>

          <div className="flex items-start space-x-3">
            <div className="mt-0.5 w-6 h-6 rounded bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center flex-shrink-0">
              <Key className="w-3.5 h-3.5 text-emerald-400" />
            </div>
            <div>
              <p className="text-sm font-semibold text-slate-200">Cryptographic Extension</p>
              <p className="text-xs text-slate-400 mt-0.5"><code className="text-violet-300 bg-violet-500/10 px-1 py-0.5 rounded">pgcrypto</code> is active and computing HMAC-SHA256 digests on triggers.</p>
            </div>
          </div>

          <div className="flex items-start space-x-3">
            <div className="mt-0.5 w-6 h-6 rounded bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center flex-shrink-0">
              <Users className="w-3.5 h-3.5 text-emerald-400" />
            </div>
            <div>
              <p className="text-sm font-semibold text-slate-200">Authentication Middleware</p>
              <p className="text-xs text-slate-400 mt-0.5">Clerk stateless JWT validation is enforcing Auditor vs HR Admin routes.</p>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}

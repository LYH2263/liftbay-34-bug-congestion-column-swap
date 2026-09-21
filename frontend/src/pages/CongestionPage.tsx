import { useEffect, useState } from "react";
import { api } from "../api/client";

type C = { floor: number; waiting: number; assigned: number; total: number };
type View = "both" | "waiting" | "assigned";

const VIEW_LABEL: Record<View, string> = {
  both: "两列合计",
  waiting: "仅候梯 waiting",
  assigned: "仅已派 assigned",
};

export default function CongestionPage() {
  const [rows, setRows] = useState<C[]>([]);
  const [view, setView] = useState<View>("both");
  const reload = () => api<C[]>("/congestion").then(setRows);
  useEffect(() => { reload(); }, []);

  const showWaiting = view !== "assigned";
  const showAssigned = view !== "waiting";
  const valueOf = (r: C) =>
    view === "waiting" ? r.waiting : view === "assigned" ? r.assigned : r.total;
  // 单列视图下隐藏该列为 0 的楼层（合计不受影响：被隐藏行该列即为 0）
  const visible = rows.filter(r => valueOf(r) > 0);
  const max = Math.max(1, ...visible.map(valueOf));
  const sumWaiting = visible.reduce((s, r) => s + r.waiting, 0);
  const sumAssigned = visible.reduce((s, r) => s + r.assigned, 0);
  const colSpan = 2 + (showWaiting ? 1 : 0) + (showAssigned ? 1 : 0) + (view === "both" ? 1 : 0);

  return (<>
    <h2>拥堵</h2>
    <div className="toolbar">
      <div className="seg">
        {(Object.keys(VIEW_LABEL) as View[]).map(v => (
          <button key={v}
            className={v === view ? "seg-btn seg-btn--on" : "seg-btn"}
            onClick={() => setView(v)}>{VIEW_LABEL[v]}</button>
        ))}
      </div>
      <button onClick={reload}>刷新</button>
    </div>
    {view === "both" && (
      <div className="congestion-legend">
        <span className="dot dot--waiting" />候梯 waiting（现网口径）
        <span className="dot dot--assigned" />已派 assigned（派工成功、清客前仍按候梯层占用）
      </div>
    )}
    <table className="table">
      <thead><tr>
        <th>楼层</th>
        {showWaiting && <th className="num">候梯 waiting</th>}
        {showAssigned && <th className="num">已派 assigned</th>}
        {view === "both" && <th className="num">合计</th>}
        <th>占用</th>
      </tr></thead>
      <tbody>
        {visible.map(r => <tr key={r.floor}>
          <td className="mono">{r.floor}F</td>
          {showWaiting && <td className="num">{r.waiting}</td>}
          {showAssigned && <td className="num">{r.assigned}</td>}
          {view === "both" && <td className="num strong">{r.total}</td>}
          <td>
            <div className="congestion-track">
              {showWaiting && r.waiting > 0 && (
                <div className="congestion-seg congestion-seg--waiting"
                  style={{ width: `${(r.waiting / max) * 220}px` }}
                  title={`waiting ${r.waiting}`} />
              )}
              {showAssigned && r.assigned > 0 && (
                <div className="congestion-seg congestion-seg--assigned"
                  style={{ width: `${(r.assigned / max) * 220}px` }}
                  title={`assigned ${r.assigned}`} />
              )}
              {view === "both" && (
                <span className="congestion-seg-num">{r.total}</span>
              )}
            </div>
          </td>
        </tr>)}
        {!visible.length && <tr><td colSpan={colSpan}>当前无候梯 / 已派拥堵</td></tr>}
      </tbody>
      {visible.length > 0 && <tfoot>
        <tr className="sum-row">
          <td>合计</td>
          {showWaiting && <td className="num strong">{sumWaiting}</td>}
          {showAssigned && <td className="num strong">{sumAssigned}</td>}
          {view === "both" && <td className="num strong">{sumWaiting + sumAssigned}</td>}
          <td />
        </tr>
      </tfoot>}
    </table>
  </>);
}

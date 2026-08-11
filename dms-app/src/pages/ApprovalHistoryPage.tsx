import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import toast from "react-hot-toast";
import { workflowApi } from "@/api/workflow.api";
import { useAuthStore } from "@/store/authStore";
import type {
  WorkflowInstance,
  WorkflowInstanceDetail,
  WorkflowHistory,
  WorkflowAction,
} from "@/types/workflow.types";

const LIMIT = 20;

const STATUS_COLORS: Record<string, string> = {
  pending_approval: "#f59e0b",
  submitted: "#3b82f6",
  approved: "#10b981",
  rejected: "#ef4444",
  returned: "#f97316",
  cancelled: "#6b7280",
};

const STATUS_LABELS: Record<string, string> = {
  pending_approval: "Pending Approval",
  submitted: "Submitted",
  approved: "Approved",
  rejected: "Rejected",
  returned: "Returned",
  cancelled: "Cancelled",
};

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function ApprovalHistoryPage() {
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);

  const [instances, setInstances] = useState<WorkflowInstance[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<WorkflowInstanceDetail | null>(null);
  const [detailHistory, setDetailHistory] = useState<WorkflowHistory[]>([]);
  const [detailActions, setDetailActions] = useState<WorkflowAction[]>([]);
  const [detailLoading, setDetailLoading] = useState(false);
  const [showModal, setShowModal] = useState(false);

  const fetchInstances = useCallback(async (skip: number) => {
    setLoading(true);
    try {
      const res = await workflowApi.getMyInstances({ skip, limit: LIMIT });
      setInstances(res.items);
      setTotal(res.total);
    } catch {
      toast.error("Failed to load submission history");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchInstances(page * LIMIT);
  }, [page, fetchInstances]);

  const openDetail = async (id: string) => {
    setSelectedId(id);
    setShowModal(true);
    setDetailLoading(true);
    setDetail(null);
    setDetailHistory([]);
    setDetailActions([]);
    try {
      const inst = await workflowApi.getInstance(id);
      setDetail(inst);
      setDetailHistory(inst.history ?? []);
      setDetailActions(inst.actions ?? []);
    } catch {
      toast.error("Failed to load instance details");
    } finally {
      setDetailLoading(false);
    }
  };

  const closeModal = () => {
    setShowModal(false);
    setSelectedId(null);
    setDetail(null);
    setDetailHistory([]);
    setDetailActions([]);
  };

  const handleCancel = async (inst: WorkflowInstance) => {
    if (!confirm(`Cancel submission for "${inst.document_title ?? "this document"}"?`)) return;
    try {
      await workflowApi.cancelInstance(inst.id);
      toast.success("Submission cancelled");
      fetchInstances(page * LIMIT);
    } catch (err: any) {
      const msg = err?.response?.data?.detail || "Failed to cancel submission";
      toast.error(msg);
    }
  };

  const TERMINAL_STATUSES = new Set(["approved", "rejected", "cancelled"]);

  const totalPages = Math.ceil(total / LIMIT);

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: "0 auto" }}>
      {/* Header card */}
      <div
        style={{
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: 8,
          padding: "16px 24px",
          marginBottom: 24,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <h1 style={{ fontSize: 20, fontWeight: 600, color: "var(--text)", margin: 0 }}>
          My Submissions
        </h1>
        <span style={{ fontSize: 14, color: "var(--text-secondary)" }}>
          {total} {total === 1 ? "submission" : "submissions"}
        </span>
      </div>

      {/* Table card */}
      <div
        style={{
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: 8,
          overflow: "hidden",
        }}
      >
        {loading ? (
          <div style={{ padding: 48, textAlign: "center", color: "var(--text-secondary)" }}>
            Loading...
          </div>
        ) : instances.length === 0 ? (
          <div style={{ padding: 48, textAlign: "center", color: "var(--text-secondary)" }}>
            No submissions found.
          </div>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                {["Document", "Workflow", "Current Step", "Status", "Submitted", "Actions"].map(
                  (h) => (
                    <th
                      key={h}
                      style={{
                        padding: "12px 16px",
                        textAlign: "left",
                        fontWeight: 600,
                        color: "var(--text-secondary)",
                        fontSize: 12,
                        textTransform: "uppercase" as const,
                        letterSpacing: 0.5,
                      }}
                    >
                      {h}
                    </th>
                  )
                )}
              </tr>
            </thead>
            <tbody>
              {instances.map((inst) => (
                <tr
                  key={inst.id}
                  style={{ borderBottom: "1px solid var(--border)" }}
                >
                  <td style={{ padding: "12px 16px", color: "var(--text)" }}>
                    {inst.document_title ?? "—"}
                  </td>
                  <td style={{ padding: "12px 16px", color: "var(--text)" }}>
                    {inst.workflow_name ?? "—"}
                  </td>
                  <td style={{ padding: "12px 16px", color: "var(--text-secondary)" }}>
                    {inst.current_step_name ?? "—"}
                  </td>
                  <td style={{ padding: "12px 16px" }}>
                    <span
                      style={{
                        display: "inline-block",
                        padding: "2px 10px",
                        borderRadius: 12,
                        fontSize: 12,
                        fontWeight: 500,
                        color: "#fff",
                        background: STATUS_COLORS[inst.status] ?? "var(--text-secondary)",
                      }}
                    >
                      {STATUS_LABELS[inst.status] ?? inst.status}
                    </span>
                  </td>
                  <td style={{ padding: "12px 16px", color: "var(--text-secondary)" }}>
                    {formatDate(inst.submitted_at)}
                  </td>
                  <td style={{ padding: "12px 16px" }}>
                    <div style={{ display: "flex", gap: 6 }}>
                      <button
                        onClick={() => openDetail(inst.id)}
                        style={{
                          background: "none",
                          border: "1px solid var(--border)",
                          borderRadius: 6,
                          padding: "4px 12px",
                          fontSize: 13,
                          color: "var(--text)",
                          cursor: "pointer",
                        }}
                      >
                        View History
                      </button>
                      {user?.id === inst.submitted_by && !TERMINAL_STATUSES.has(inst.status) && (
                        <button
                          onClick={() => handleCancel(inst)}
                          style={{
                            background: "none",
                            border: "1px solid #fca5a5",
                            borderRadius: 6,
                            padding: "4px 12px",
                            fontSize: 13,
                            color: "#dc2626",
                            cursor: "pointer",
                          }}
                        >
                          Cancel
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 8,
              padding: "12px 16px",
              borderTop: "1px solid var(--border)",
            }}
          >
            <button
              disabled={page === 0}
              onClick={() => setPage((p) => p - 1)}
              style={{
                padding: "4px 12px",
                borderRadius: 6,
                border: "1px solid var(--border)",
                background: "var(--surface)",
                color: page === 0 ? "var(--text-tertiary)" : "var(--text)",
                cursor: page === 0 ? "default" : "pointer",
                fontSize: 13,
              }}
            >
              Previous
            </button>
            <span style={{ fontSize: 13, color: "var(--text-secondary)" }}>
              Page {page + 1} of {totalPages}
            </span>
            <button
              disabled={page >= totalPages - 1}
              onClick={() => setPage((p) => p + 1)}
              style={{
                padding: "4px 12px",
                borderRadius: 6,
                border: "1px solid var(--border)",
                background: "var(--surface)",
                color: page >= totalPages - 1 ? "var(--text-tertiary)" : "var(--text)",
                cursor: page >= totalPages - 1 ? "default" : "pointer",
                fontSize: 13,
              }}
            >
              Next
            </button>
          </div>
        )}
      </div>

      {/* Detail modal */}
      {showModal && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 1000,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: "rgba(0,0,0,0.4)",
          }}
          onClick={closeModal}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              background: "var(--surface)",
              border: "1px solid var(--border)",
              borderRadius: 12,
              width: "100%",
              maxWidth: 680,
              maxHeight: "85vh",
              display: "flex",
              flexDirection: "column",
              overflow: "hidden",
            }}
          >
            {/* Modal header */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "16px 24px",
                borderBottom: "1px solid var(--border)",
              }}
            >
              <h2 style={{ margin: 0, fontSize: 18, fontWeight: 600, color: "var(--text)" }}>
                Submission History
              </h2>
              <button
                onClick={closeModal}
                style={{
                  background: "none",
                  border: "none",
                  fontSize: 20,
                  cursor: "pointer",
                  color: "var(--text-secondary)",
                  lineHeight: 1,
                }}
              >
                &times;
              </button>
            </div>

            {/* Modal body */}
            <div style={{ overflowY: "auto", padding: 24, flex: 1 }}>
              {detailLoading ? (
                <div style={{ textAlign: "center", color: "var(--text-secondary)", padding: 32 }}>
                  Loading details...
                </div>
              ) : detail ? (
                <>
                  {/* Instance info */}
                  <div
                    style={{
                      background: "var(--surface)",
                      border: "1px solid var(--border)",
                      borderRadius: 8,
                      padding: 16,
                      marginBottom: 24,
                    }}
                  >
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                      <div>
                        <div style={{ fontSize: 12, color: "var(--text-tertiary)", marginBottom: 2 }}>
                          Document
                        </div>
                        <div style={{ fontSize: 14, color: "var(--text)", fontWeight: 500 }}>
                          {detail.document_title ?? "—"}
                        </div>
                      </div>
                      <div>
                        <div style={{ fontSize: 12, color: "var(--text-tertiary)", marginBottom: 2 }}>
                          Workflow
                        </div>
                        <div style={{ fontSize: 14, color: "var(--text)", fontWeight: 500 }}>
                          {detail.workflow_name ?? "—"}
                        </div>
                      </div>
                      <div>
                        <div style={{ fontSize: 12, color: "var(--text-tertiary)", marginBottom: 2 }}>
                          Status
                        </div>
                        <span
                          style={{
                            display: "inline-block",
                            padding: "2px 10px",
                            borderRadius: 12,
                            fontSize: 12,
                            fontWeight: 500,
                            color: "#fff",
                            background: STATUS_COLORS[detail.status] ?? "var(--text-secondary)",
                          }}
                        >
                          {STATUS_LABELS[detail.status] ?? detail.status}
                        </span>
                      </div>
                      <div>
                        <div style={{ fontSize: 12, color: "var(--text-tertiary)", marginBottom: 2 }}>
                          Submitted
                        </div>
                        <div style={{ fontSize: 14, color: "var(--text-secondary)" }}>
                          {formatDate(detail.submitted_at)}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Timeline */}
                  <h3 style={{ fontSize: 14, fontWeight: 600, color: "var(--text)", margin: "0 0 16px" }}>
                    Approval Timeline
                  </h3>

                  {detailHistory.length === 0 ? (
                    <div style={{ color: "var(--text-secondary)", fontSize: 14 }}>
                      No history records yet.
                    </div>
                  ) : (
                    <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
                      {detailHistory.map((entry, idx) => (
                        <div
                          key={entry.id}
                          style={{
                            display: "flex",
                            gap: 16,
                            position: "relative",
                          }}
                        >
                          {/* Left line */}
                          <div
                            style={{
                              display: "flex",
                              flexDirection: "column",
                              alignItems: "center",
                              width: 20,
                              flexShrink: 0,
                            }}
                          >
                            <div
                              style={{
                                width: 10,
                                height: 10,
                                borderRadius: "50%",
                                background: "var(--text-secondary)",
                                marginTop: 6,
                                zIndex: 1,
                              }}
                            />
                            {idx < detailHistory.length - 1 && (
                              <div
                                style={{
                                  width: 2,
                                  flex: 1,
                                  background: "var(--border)",
                                  minHeight: 24,
                                }}
                              />
                            )}
                          </div>

                          {/* Entry content */}
                          <div
                            style={{
                              flex: 1,
                              paddingBottom: idx < detailHistory.length - 1 ? 20 : 0,
                            }}
                          >
                            <div style={{ fontSize: 14, fontWeight: 500, color: "var(--text)" }}>
                              {entry.event_type}
                            </div>
                            {entry.actor_name && (
                              <div style={{ fontSize: 13, color: "var(--text-secondary)", marginTop: 2 }}>
                                by {entry.actor_name}
                                {entry.designation_snapshot && (
                                  <span style={{ color: "var(--text-tertiary)" }}>
                                    {" "}
                                    &middot; {entry.designation_snapshot}
                                  </span>
                                )}
                              </div>
                            )}
                            {entry.remarks && (
                              <div
                                style={{
                                  fontSize: 13,
                                  color: "var(--text-secondary)",
                                  marginTop: 4,
                                  fontStyle: "italic",
                                }}
                              >
                                {entry.remarks}
                              </div>
                            )}
                            <div style={{ fontSize: 12, color: "var(--text-tertiary)", marginTop: 4 }}>
                              {formatDate(entry.occurred_at)}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Approval Actions */}
                  {detailActions.length > 0 && (
                    <>
                      <h3 style={{ fontSize: 14, fontWeight: 600, color: "var(--text)", margin: "24px 0 16px" }}>
                        Approval Actions
                      </h3>
                      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                        {detailActions.map((action) => (
                          <ActionWithSignature key={action.id} action={action} />
                        ))}
                      </div>
                    </>
                  )}
                </>
              ) : (
                <div style={{ textAlign: "center", color: "var(--text-secondary)", padding: 32 }}>
                  No details available.
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

const ACTION_COLORS: Record<string, string> = {
  approve: "#10b981",
  reject: "#ef4444",
  return: "#f97316",
  clarify: "#3b82f6",
};

function ActionWithSignature({ action }: { action: WorkflowAction }) {
  const [sigUrl, setSigUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!action.signature_id) return;
    let revoked = false;
    workflowApi.getSignatureFileUrl(action.signature_id).then((url) => {
      if (!revoked) setSigUrl(url);
    });
    return () => {
      revoked = true;
      if (sigUrl) URL.revokeObjectURL(sigUrl);
    };
  }, [action.signature_id]);

  const color = ACTION_COLORS[action.action] ?? "var(--text-secondary)";

  return (
    <div
      style={{
        border: "1px solid var(--border)",
        borderRadius: 8,
        padding: 12,
        display: "flex",
        gap: 12,
        alignItems: sigUrl ? "flex-start" : "center",
        flexDirection: sigUrl ? "column" : "row",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8, flex: 1 }}>
        <span
          style={{
            display: "inline-block",
            padding: "2px 10px",
            borderRadius: 12,
            fontSize: 12,
            fontWeight: 500,
            color: "#fff",
            background: color,
            textTransform: "capitalize",
          }}
        >
          {action.action}
        </span>
        <span style={{ fontSize: 13, color: "var(--text)" }}>
          {action.acted_by_name ?? `User #${action.acted_by}`}
        </span>
        <span style={{ fontSize: 12, color: "var(--text-tertiary)" }}>
          {formatDate(action.acted_at)}
        </span>
      </div>
      {action.remarks && (
        <div style={{ fontSize: 13, color: "var(--text-secondary)", fontStyle: "italic" }}>
          {action.remarks}
        </div>
      )}
      {sigUrl && (
        <div>
          <div style={{ fontSize: 11, color: "var(--text-tertiary)", marginBottom: 4 }}>Signature</div>
          <img
            src={sigUrl}
            alt="Approval signature"
            style={{ maxHeight: 60, display: "block", border: "1px solid var(--border)", borderRadius: 4, padding: 4, backgroundColor: "#fff" }}
          />
        </div>
      )}
    </div>
  );
}

/**
 * BidWin Agent 프론트엔드 JavaScript
 * API 호출, 결과 표시, Human-in-the-Loop 루프 관리
 */

const API_BASE = "http://localhost:8000/api";
let selectedBid = null;
let currentResult = null;
let logs = [];
let allBids = [];
let filteredBids = [];
let filterDebounceTimer = null;

function addLog(message, type = "info") {
    const timestamp = new Date().toLocaleTimeString("ko-KR");
    const logEntry = `[${timestamp}] [${type.toUpperCase()}] ${message}`;
    logs.push(logEntry);

    const logsContainer = document.getElementById("logs-container");
    const logEl = document.createElement("div");
    logEl.className = `log-entry ${type}`;
    logEl.textContent = logEntry;
    logsContainer.appendChild(logEl);
    logsContainer.scrollTop = logsContainer.scrollHeight;
}

document.addEventListener("DOMContentLoaded", () => {
    addLog("BidWin Agent 대시보드 로드 완료", "info");

    document.getElementById("btn-search-bids").addEventListener("click", searchBids);
    document.getElementById("btn-reset-filters").addEventListener("click", resetBidFilters);
    document.getElementById("btn-generate-proposal").addEventListener("click", generateProposal);
    document.getElementById("btn-revise-proposal").addEventListener("click", reviseProposal);
    document.getElementById("bid-pdf-file").addEventListener("change", updatePdfStatus);
    bindBidFilterEvents();
    updatePdfStatus();
    searchBids();
});

async function searchBids() {
    const filters = getBidFilters();
    addLog(`입찰공고 자동 수집 시작 (${filters.businessType})`, "info");
    setFilterSummary("실제 공고를 조회하는 중입니다.", "필터 조건에 맞춰 목록을 다시 정리합니다.");

    try {
        const response = await fetch(`${API_BASE}/bids/search`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                keyword: null,
                business_type: filters.businessType
            })
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(errorText || "공고 검색 요청 실패");
        }

        const payload = await response.json();
        allBids = (payload.items || []).map((bid) => ({
            ...bid,
            budgetDisplay: formatCurrency(bid.estimatedAmount || bid.budget),
            numericBudget: toNumber(bid.estimatedAmount || bid.budget),
            deadlineDate: parseBidDate(bid.deadline),
            matchScore: null,
            strengths: bid.agency ? [bid.agency] : []
        }));

        addLog(`${allBids.length}개 실제 공고 수집 완료`, "success");
        applyBidFilters();
    } catch (error) {
        document.getElementById("no-bids-msg").style.display = "block";
        setFilterSummary("공고를 불러오지 못했습니다.", "네트워크 또는 API 상태를 확인해주세요.");
        addLog(`공고 수집 실패: ${error.message}`, "error");
    }
}

function bindBidFilterEvents() {
    const filterIds = [
        "filter-company-name",
        "filter-business-domain",
        "filter-company-skills",
        "filter-company-credentials",
        "filter-budget-min",
        "filter-budget-max",
        "filter-deadline-from",
        "filter-deadline-to"
    ];

    filterIds.forEach((id) => {
        const element = document.getElementById(id);
        if (!element) return;
        element.addEventListener("input", debounceApplyBidFilters);
        element.addEventListener("change", debounceApplyBidFilters);
    });

    const businessTypeSelect = document.getElementById("filter-business-type");
    if (businessTypeSelect) {
        businessTypeSelect.addEventListener("change", () => {
            addLog(`업무구분 필터 변경: ${businessTypeSelect.value}`, "info");
            searchBids();
        });
    }
}

function debounceApplyBidFilters() {
    window.clearTimeout(filterDebounceTimer);
    filterDebounceTimer = window.setTimeout(() => {
        applyBidFilters();
    }, 180);
}

function applyBidFilters() {
    const filters = getBidFilters();
    const activeKeywords = buildCompanyKeywords(filters);

    filteredBids = allBids
        .map((bid) => enrichBidWithFit(bid, activeKeywords))
        .filter((bid) => passesBidFilters(bid, filters, activeKeywords))
        .sort((a, b) => {
            if ((b.fitScore || 0) !== (a.fitScore || 0)) {
                return (b.fitScore || 0) - (a.fitScore || 0);
            }
            return (b.numericBudget || 0) - (a.numericBudget || 0);
        });

    displayBids(filteredBids);
    updateSelectionAfterFiltering();

    const summaryMessage = `전체 ${allBids.length}건 중 ${filteredBids.length}건 표시`;
    const hintMessage = activeKeywords.length > 0
        ? `회사 키워드 ${activeKeywords.length}개와 금액·기간 조건을 함께 반영했습니다.`
        : "회사 정보가 비어 있으면 금액·기간 조건만 적용합니다.";
    setFilterSummary(summaryMessage, hintMessage);

    addLog(`필터 적용 완료: ${filteredBids.length}개 공고 표시`, "info");
}

function displayBids(bids) {
    const bidsList = document.getElementById("bids-list");
    const noMsg = document.getElementById("no-bids-msg");
    bidsList.innerHTML = "";

    if (!Array.isArray(bids) || bids.length === 0) {
        noMsg.style.display = "block";
        noMsg.textContent = "표시할 공고가 없습니다.";
        return;
    }

    noMsg.style.display = "none";

    bids.forEach((bid) => {
        const bidCard = document.createElement("div");
        bidCard.className = "bid-card";
        bidCard.innerHTML = `
            <h3>${bid.title}</h3>
            <div class="bid-meta">
                <span class="badge">${bid.businessType}</span>
                <span class="badge">${bid.budgetDisplay || bid.budget || "-"}</span>
            </div>
            <div class="bid-meta">마감: ${bid.deadline}</div>
            <div class="bid-meta">발주기관: ${bid.agency || "-"}</div>
            ${renderFitSummary(bid)}
            <button class="card-action-button" data-bid-id="${bid.id}">이 공고 선택</button>
        `;
        if (selectedBid?.id === bid.id) {
            bidCard.classList.add("selected");
        }
        bidCard.addEventListener("click", (event) => {
            if (event.target instanceof HTMLElement && event.target.closest(".card-action-button")) {
                selectBid(bid);
                focusProposalSetup();
                return;
            }
            selectBid(bid);
        });
        bidsList.appendChild(bidCard);
    });
}

function selectBid(bid) {
    const previousBidId = selectedBid?.id;
    selectedBid = bid;
    currentResult = null;
    resetFeedbackPanel({ preservePdf: previousBidId === bid.id });
    highlightSelectedBid();
    addLog(`PM이 공고 선택: "${bid.title}"`, "info");

    const infoDiv = document.getElementById("selected-bid-info");
    const companyProfile = buildCompanyProfilePayload();
    infoDiv.innerHTML = `
        <h3>선택된 공고</h3>
        <p><strong>${bid.title}</strong></p>
        <p>예산: ${bid.budgetDisplay || bid.budget || "-"} | 마감: ${bid.deadline}</p>
        <p>발주기관: ${bid.agency || "-"}</p>
        <p>회사 기준: ${companyProfile.name || "입력 안 함"}${companyProfile.skills.length ? ` | 핵심 역량: ${companyProfile.skills.join(", ")}` : ""}</p>
    `;
    focusProposalSetup();
}

async function generateProposal() {
    if (!selectedBid) {
        addLog("공고를 먼저 선택하세요", "error");
        return;
    }

    const pdfInput = document.getElementById("bid-pdf-file");
    const uploadedFile = pdfInput?.files?.[0] || null;
    const isPdfMode = Boolean(uploadedFile);

    addLog(
        isPdfMode
            ? `PDF 기반 작성 시작: ${uploadedFile.name}`
            : "메타데이터 기반 자동 작성 시작",
        "agent"
    );

    try {
        const formData = new FormData();
        formData.append("keyword", selectedBid.title || "");
        formData.append("business_type", selectedBid.businessType || "용역");
        formData.append("company_id", "COMPANY_A");
        formData.append("company_profile", JSON.stringify(buildCompanyProfilePayload()));
        if (uploadedFile) {
            formData.append("pdf_file", uploadedFile);
        }

        const response = await fetch(`${API_BASE}/orchestrator/stream-upload`, {
            method: "POST",
            body: formData
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(errorText || "서버 요청 실패");
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let finalResult = null;

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop();

            for (const line of lines) {
                if (!line.trim()) continue;
                let event;
                try {
                    event = JSON.parse(line);
                } catch (error) {
                    continue;
                }

                if (event.type === "log") {
                    addLog(event.message, "agent");
                } else if (event.type === "error") {
                    addLog(`서버 에러: ${event.message}`, "error");
                } else if (event.type === "result") {
                    finalResult = event.payload;
                }
            }
        }

        if (!finalResult) {
            throw new Error("최종 결과를 받지 못했습니다.");
        }

        currentResult = finalResult;
        addLog("초안 생성 완료", "success");
        showProposalResult(finalResult);
        activateFeedbackPanel(finalResult);
        focusProposalResult();
    } catch (error) {
        addLog(`제안서 생성 실패: ${error.message}`, "error");
    }
}

async function reviseProposal() {
    if (!currentResult) {
        addLog("먼저 제안서를 생성하세요", "error");
        return;
    }

    const feedbackText = document.getElementById("feedback-text").value.trim();
    const feedbackMode = document.getElementById("feedback-mode").value;
    const sectionRequest = document.getElementById("feedback-section-request").value.trim();
    const toneStrength = document.getElementById("feedback-tone-strength").value;

    if (!feedbackText) {
        addLog("PM 피드백을 입력하세요", "error");
        return;
    }

    const reviseButton = document.getElementById("btn-revise-proposal");
    reviseButton.disabled = true;
    addLog(`PM 피드백 반영 시작 (${feedbackMode})`, "agent");

    try {
        const response = await fetch(`${API_BASE}/orchestrator/revise`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                base_result: currentResult,
                feedback_text: feedbackText,
                feedback_mode: feedbackMode,
                section_request: sectionRequest,
                tone_strength: toneStrength
            })
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(errorText || "피드백 반영 실패");
        }

        const revisedResult = await response.json();
        currentResult = revisedResult;

        addLog("Revision Agent가 수정본 생성 완료", "success");
        if (Array.isArray(revisedResult.logs)) {
            revisedResult.logs.forEach((message) => addLog(message, "agent"));
        }

        showProposalResult(revisedResult);
        activateFeedbackPanel(revisedResult);
        focusProposalResult();
        document.getElementById("feedback-text").value = "";
        addLog("수정본 제안서를 화면에 갱신했습니다.", "success");
    } catch (error) {
        addLog(`피드백 반영 실패: ${error.message}`, "error");
    } finally {
        reviseButton.disabled = false;
    }
}

function showProposalResult(result) {
    const resultDiv = document.getElementById("proposal-result");
    const docxUrl = result?.files?.docx ? `${window.location.origin}${result.files.docx}` : null;
    const xlsxUrl = result?.files?.xlsx ? `${window.location.origin}${result.files.xlsx}` : null;
    const candidate = result?.candidate || selectedBid || {};
    const evaluation = result?.evaluation || {};
    const assessment = result?.assessment || {};
    const matchResult = result?.match_result || {};
    const revisionHistory = result?.memory?.revision_history || [];
    const proposalText = result?.proposal?.draft_text || "";
    const documentParse = result?.memory?.document_parse || null;
    const preview = escapeHtml(proposalText).replace(/\n/g, "<br>");
    const isRevised = revisionHistory.length > 0;

    resultDiv.className = "proposal-result show success";
    resultDiv.innerHTML = `
        <div class="proposal-result-head">
            <h3>${isRevised ? "수정된 제안서 결과" : "제안서 생성 결과"}</h3>
            <span class="result-status-chip">${isRevised ? `Revision ${revisionHistory.length}` : "초안"}</span>
        </div>
        <p><strong>${candidate.title || ""}</strong></p>
        <div class="result-grid">
            <div class="result-metric">
                <span class="metric-label">Win Probability</span>
                <strong>${matchResult.win_probability ?? "-"}%</strong>
            </div>
            <div class="result-metric">
                <span class="metric-label">자격 매칭</span>
                <strong>${assessment.match_score ?? "-"}%</strong>
            </div>
            <div class="result-metric">
                <span class="metric-label">리스크 점수</span>
                <strong>${evaluation.risk_score ?? "-"}</strong>
            </div>
        </div>
        <p>제안서 초안: ${docxUrl ? `<a href="${docxUrl}" target="_blank">다운로드</a>` : "생성 실패"}</p>
        <p>평가 매트릭스: ${xlsxUrl ? `<a href="${xlsxUrl}" target="_blank">다운로드</a>` : "생성 실패"}</p>
        <div class="proposal-preview">
            <h4>${isRevised ? "수정본 미리보기" : "초안 미리보기"}</h4>
            <div class="proposal-preview-body">${preview || "초안 없음"}</div>
        </div>
        ${renderScoreExplanation(matchResult, assessment)}
        ${renderDocumentParseInfo(documentParse, result?.memory?.source_mode)}
        <div class="recommendations-box">
            <h4>Red Team 코멘트</h4>
            ${renderList(evaluation.recommendations, "권고사항이 아직 없습니다.")}
        </div>
    `;
}

function activateFeedbackPanel(result) {
    const panel = document.getElementById("feedback-panel");
    const emptyMsg = document.getElementById("feedback-empty-msg");
    const reviseButton = document.getElementById("btn-revise-proposal");
    const revisionSummary = document.getElementById("revision-summary");
    const downloadActions = document.getElementById("feedback-download-actions");
    const revisionHistory = result?.memory?.revision_history || [];

    panel.classList.remove("hidden");
    emptyMsg.style.display = "none";
    reviseButton.disabled = false;
    downloadActions.innerHTML = renderDownloadActions(result);

    revisionSummary.innerHTML = `
        <h4>반복 개선 상태</h4>
        <p>현재 revision 횟수: <strong>${revisionHistory.length}</strong></p>
        <p>최신 리스크 점수: <strong>${result?.evaluation?.risk_score ?? "-"}</strong></p>
        ${revisionHistory.length > 0 ? renderRevisionHistory(revisionHistory) : "<p class=\"muted\">아직 PM 피드백 반영 이력이 없습니다.</p>"}
    `;
}

function resetFeedbackPanel(options = {}) {
    const preservePdf = Boolean(options.preservePdf);
    document.getElementById("feedback-panel").classList.add("hidden");
    document.getElementById("feedback-empty-msg").style.display = "block";
    document.getElementById("btn-revise-proposal").disabled = true;
    document.getElementById("feedback-text").value = "";
    document.getElementById("feedback-section-request").value = "";
    document.getElementById("feedback-tone-strength").value = "";
    document.getElementById("revision-summary").innerHTML = "";
    document.getElementById("feedback-download-actions").innerHTML = "";
    document.getElementById("proposal-result").className = "proposal-result";
    document.getElementById("proposal-result").innerHTML = "";
    const pdfInput = document.getElementById("bid-pdf-file");
    if (pdfInput && !preservePdf) {
        pdfInput.value = "";
    }
    updatePdfStatus();
}

function renderList(items, emptyMessage) {
    if (!Array.isArray(items) || items.length === 0) {
        return `<p class="muted">${emptyMessage}</p>`;
    }
    return `<ul>${items.map((item) => `<li>${escapeHtml(String(item))}</li>`).join("")}</ul>`;
}

function renderRevisionHistory(history) {
    return `
        <ul class="revision-history">
            ${history.slice().reverse().map((entry, index) => `
                <li>
                    <strong>Revision ${history.length - index}</strong>
                    <span>리스크: ${entry.previous_risk_score ?? "-"} → ${entry.new_risk_score ?? "-"}</span>
                    <div>${escapeHtml(entry.feedback || "")}</div>
                </li>
            `).join("")}
        </ul>
    `;
}

function escapeHtml(value) {
    return value
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function formatCurrency(value) {
    const numeric = Number(String(value || "").replace(/[^\d.-]/g, ""));
    if (!Number.isFinite(numeric) || numeric <= 0) {
        return value || "-";
    }
    return `${numeric.toLocaleString("ko-KR")}원`;
}

function focusProposalResult() {
    const proposalSection = document.getElementById("proposal-section");
    if (proposalSection) {
        proposalSection.scrollIntoView({ behavior: "smooth", block: "start" });
    }
}

function focusProposalSetup() {
    const proposalSection = document.getElementById("proposal-section");
    if (proposalSection) {
        proposalSection.scrollIntoView({ behavior: "smooth", block: "start" });
    }
}

function updatePdfStatus() {
    const pdfInput = document.getElementById("bid-pdf-file");
    const status = document.getElementById("bid-pdf-status");
    const file = pdfInput?.files?.[0] || null;
    if (!status) {
        return;
    }
    if (file) {
        status.textContent = `선택된 PDF: ${file.name}`;
        return;
    }
    status.textContent = "아직 업로드한 PDF가 없습니다.";
}

function renderDownloadActions(result) {
    const docxUrl = result?.files?.docx ? `${window.location.origin}${result.files.docx}` : null;
    const xlsxUrl = result?.files?.xlsx ? `${window.location.origin}${result.files.xlsx}` : null;
    const links = [];
    if (docxUrl) {
        links.push(`<a class="inline-download-button" href="${docxUrl}" target="_blank">최신 제안서 다운로드</a>`);
    }
    if (xlsxUrl) {
        links.push(`<a class="inline-download-button" href="${xlsxUrl}" target="_blank">최신 평가표 다운로드</a>`);
    }
    return links.join("");
}

function renderDocumentParseInfo(documentParse, sourceMode) {
    if (!documentParse && sourceMode !== "metadata_only") {
        return "";
    }

    if (sourceMode === "metadata_only") {
        return `
            <div class="parse-info-box">
                <h4>문서 입력 방식</h4>
                <p class="muted">PDF를 업로드하지 않아 공고 메타데이터만으로 초안을 작성했습니다.</p>
            </div>
        `;
    }

    const candidate = currentResult?.candidate || {};
    const summary = candidate.document_summary || {};
    const requirements = Array.isArray(candidate.requirements) ? candidate.requirements : [];
    const summaryLines = [];
    if (summary.estimated_amount) {
        summaryLines.push(`추정금액 ${formatCurrency(summary.estimated_amount)}`);
    }
    if (summary.estimated_price) {
        summaryLines.push(`추정가격 ${formatCurrency(summary.estimated_price)}`);
    }
    if (summary.schedule?.bid_close) {
        summaryLines.push(`마감 ${summary.schedule.bid_close}`);
    }
    const requirementItems = requirements
        .slice(0, 8)
        .map((item) => `${item.type || "요건"}: ${summarizeDisplayText(item.text, 90)}`);
    const submissionDocs = Array.isArray(summary.submission_docs)
        ? summary.submission_docs.slice(0, 6).map((item) => summarizeDisplayText(item, 90))
        : [];

    return `
        <div class="parse-info-box">
            <h4>PDF 파싱 확인</h4>
            <div class="parse-info-grid">
                <div class="parse-info-item"><strong>파일명</strong><br>${escapeHtml(documentParse?.filename || "-")}</div>
                <div class="parse-info-item"><strong>파싱 방식</strong><br>${escapeHtml(documentParse?.parse_method || "-")}</div>
                <div class="parse-info-item"><strong>섹션 수</strong><br>${documentParse?.section_count ?? 0}</div>
                <div class="parse-info-item"><strong>원본 경로</strong><br>${escapeHtml(documentParse?.source || "-")}</div>
            </div>
            <div class="parse-preview">
                <strong>추출된 핵심 기준</strong>
                ${summaryLines.length ? `<div>${escapeHtml(summaryLines.join(" | "))}</div>` : `<div class="muted">금액/일정 요약을 아직 잡지 못했습니다.</div>`}
                <br>
                <strong>평가항목 / 필수요건</strong>
                ${renderList(requirementItems, "공고 기준/평가항목을 아직 충분히 추출하지 못했습니다.")}
                <strong>제출서류</strong>
                ${renderList(submissionDocs, "제출서류 항목을 아직 찾지 못했습니다.")}
            </div>
        </div>
    `;
}

function renderScoreExplanation(matchResult, assessment) {
    const matchDetails = Array.isArray(matchResult?.details) ? matchResult.details : [];
    const assessmentDetails = Array.isArray(assessment?.details) ? assessment.details : [];
    const lowItems = matchDetails
        .slice()
        .sort((a, b) => (a.score || 0) - (b.score || 0))
        .slice(0, 4);
    const missingItems = assessmentDetails.filter((item) => item.status === "missing").slice(0, 4);
    const reviewItems = assessmentDetails.filter((item) => item.status === "review_needed").slice(0, 3);

    return `
        <div class="recommendations-box">
            <h4>매칭 / 평가 근거</h4>
            <p>자격 매칭은 요구사항별 회사 스킬·인증·실적·요약 정보의 키워드 겹침과 절차성 항목 보정으로 계산합니다. 리스크 점수는 미충족 요건, 낮은 적합도, 과한 표현 여부를 합산해 산출합니다.</p>
            <p><strong>낮게 잡힌 요구사항</strong></p>
            ${renderList(lowItems.map((item) => `${summarizeDisplayText(item.text, 90)} (${item.score}점)`), "낮은 점수 항목이 아직 없습니다.")}
            <p><strong>미충족 판단 항목</strong></p>
            ${renderList(missingItems.map((item) => `${item.req} - 추가 증빙 필요`), "미충족 항목이 없습니다.")}
            <p><strong>보완 서류 중심 항목</strong></p>
            ${renderList(reviewItems.map((item) => `${item.req} - 증빙/계획 보강 권장`), "보완 서류 중심 항목이 없습니다.")}
        </div>
    `;
}

function summarizeDisplayText(text, maxLength = 90) {
    let normalized = String(text || "").replace(/\s+/g, " ").trim();
    const stopMarkers = [
        "제안서 작성 요령",
        "작성지침",
        "작성서식",
        "주의사항",
        "문의처",
        "입찰참가신청서",
        "입찰서",
        "청렴계약이행 서약서",
        "서 약 서"
    ];

    stopMarkers.forEach((marker) => {
        const index = normalized.indexOf(marker);
        if (index > 0) {
            normalized = normalized.slice(0, index).trim();
        }
    });

    normalized = normalized.split(/\s(?=가\.|나\.|다\.|라\.|마\.|바\.)/)[0].trim();
    if (normalized.length > maxLength) {
        normalized = normalized.slice(0, maxLength).trimEnd() + "...";
    }
    return normalized;
}

function getBidFilters() {
    return {
        companyName: document.getElementById("filter-company-name")?.value.trim() || "",
        businessType: document.getElementById("filter-business-type")?.value || "용역",
        businessDomain: document.getElementById("filter-business-domain")?.value.trim() || "",
        companySkills: document.getElementById("filter-company-skills")?.value.trim() || "",
        companyCredentials: document.getElementById("filter-company-credentials")?.value.trim() || "",
        minBudget: toNumber(document.getElementById("filter-budget-min")?.value),
        maxBudget: toNumber(document.getElementById("filter-budget-max")?.value),
        deadlineFrom: document.getElementById("filter-deadline-from")?.value || "",
        deadlineTo: document.getElementById("filter-deadline-to")?.value || ""
    };
}

function buildCompanyProfilePayload() {
    const filters = getBidFilters();
    const skills = splitInputValues(filters.companySkills);
    const certifications = splitInputValues(filters.companyCredentials);
    const businessParts = [filters.businessDomain, filters.companySkills, filters.companyCredentials].filter(Boolean);

    return {
        company_id: "USER_INPUT_PROFILE",
        name: filters.companyName || "입력된 회사 정보",
        summary: businessParts.join(" / ") || "사용자가 입력한 회사 정보 기반 임시 프로필",
        skills,
        certifications,
        projects: certifications.map((item) => ({ title: item, year: null, role: "기입 정보", value: null })),
        headcount: null
    };
}

function buildCompanyKeywords(filters) {
    return Array.from(new Set([
        ...tokenizeFilterText(filters.businessDomain),
        ...tokenizeFilterText(filters.companySkills),
        ...tokenizeFilterText(filters.companyCredentials)
    ])).slice(0, 24);
}

function tokenizeFilterText(text) {
    return splitInputValues(text)
        .flatMap((value) => String(value).toLowerCase().split(/[^a-z0-9가-힣]+/))
        .map((value) => value.trim())
        .filter((value) => value.length >= 2);
}

function splitInputValues(text) {
    return String(text || "")
        .split(/[\n,\/]+/)
        .map((item) => item.trim())
        .filter(Boolean);
}

function enrichBidWithFit(bid, activeKeywords) {
    const haystack = `${bid.title || ""} ${bid.agency || ""} ${bid.businessType || ""}`.toLowerCase();
    const matchedKeywords = activeKeywords.filter((keyword) => haystack.includes(keyword));
    const fitScore = activeKeywords.length === 0
        ? null
        : Math.min(100, Math.round((matchedKeywords.length / activeKeywords.length) * 100));

    return {
        ...bid,
        matchedKeywords,
        fitScore
    };
}

function passesBidFilters(bid, filters, activeKeywords) {
    if (Number.isFinite(filters.minBudget) && Number.isFinite(bid.numericBudget) && bid.numericBudget < filters.minBudget) {
        return false;
    }
    if (Number.isFinite(filters.maxBudget) && Number.isFinite(bid.numericBudget) && bid.numericBudget > filters.maxBudget) {
        return false;
    }

    const bidDate = bid.deadlineDate;
    const fromDate = filters.deadlineFrom ? new Date(`${filters.deadlineFrom}T00:00:00`) : null;
    const toDate = filters.deadlineTo ? new Date(`${filters.deadlineTo}T23:59:59`) : null;

    if (fromDate && bidDate && bidDate < fromDate) {
        return false;
    }
    if (toDate && bidDate && bidDate > toDate) {
        return false;
    }

    if (activeKeywords.length > 0 && (!bid.matchedKeywords || bid.matchedKeywords.length === 0)) {
        return false;
    }

    return true;
}

function renderFitSummary(bid) {
    if (!Array.isArray(bid.matchedKeywords) || bid.matchedKeywords.length === 0) {
        return "";
    }

    const tags = bid.matchedKeywords
        .slice(0, 4)
        .map((keyword) => `<span class="fit-tag">${escapeHtml(keyword)}</span>`)
        .join("");

    return `
        <div class="fit-summary">
            <span class="fit-score">회사 적합도 ${bid.fitScore ?? 0}%</span>
            <div class="fit-tags">${tags}</div>
        </div>
    `;
}

function setFilterSummary(countMessage, hintMessage) {
    const countEl = document.getElementById("filter-result-count");
    const hintEl = document.getElementById("filter-result-hint");
    if (countEl) {
        countEl.textContent = countMessage;
    }
    if (hintEl) {
        hintEl.textContent = hintMessage;
    }
}

function updateSelectionAfterFiltering() {
    if (!selectedBid) {
        highlightSelectedBid();
        return;
    }

    const stillVisible = filteredBids.some((bid) => bid.id === selectedBid.id);
    if (stillVisible) {
        highlightSelectedBid();
        return;
    }

    selectedBid = null;
    const infoDiv = document.getElementById("selected-bid-info");
    infoDiv.innerHTML = "<p class=\"muted\">필터 결과에 맞는 공고를 선택하면 여기서 바로 제안서 생성을 이어갈 수 있습니다.</p>";
    highlightSelectedBid();
}

function highlightSelectedBid() {
    document.querySelectorAll(".bid-card").forEach((card) => {
        const button = card.querySelector(".card-action-button");
        const bidId = button?.getAttribute("data-bid-id");
        card.classList.toggle("selected", Boolean(selectedBid && bidId === selectedBid.id));
    });
}

function resetBidFilters() {
    [
        "filter-company-name",
        "filter-business-domain",
        "filter-company-skills",
        "filter-company-credentials",
        "filter-budget-min",
        "filter-budget-max",
        "filter-deadline-from",
        "filter-deadline-to"
    ].forEach((id) => {
        const element = document.getElementById(id);
        if (!element) return;
        element.value = "";
    });
    document.getElementById("filter-business-type").value = "용역";
    addLog("회사 정보 및 금액·기간 필터 초기화", "info");
    searchBids();
}

function parseBidDate(value) {
    if (!value) {
        return null;
    }
    const normalized = String(value).trim().replace(" ", "T");
    const parsed = new Date(normalized);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function toNumber(value) {
    const numeric = Number(String(value ?? "").replace(/[^\d.-]/g, ""));
    return Number.isFinite(numeric) && numeric > 0 ? numeric : null;
}

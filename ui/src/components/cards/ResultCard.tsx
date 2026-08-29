import { FileBarChart } from "lucide-react";
import { useChatStore, type ResultEntry } from "../../store/chatStore";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card, CardHeader, CardSection } from "../ui/Card";

export interface ResultCardProps {
  readonly result: ResultEntry;
}

/**
 * Card for a `result_ready` event. Opening the result selects it and, when
 * needed, fetches the payload from the ResultStore
 * (`GET /api/v1/results/{result_id}`) for the ResultViewer.
 */
export function ResultCard({ result }: ResultCardProps) {
  const selectResult = useChatStore((s) => s.selectResult);
  const loadResult = useChatStore((s) => s.loadResult);

  const open = () => {
    selectResult(result.resultId);
    if (!result.loading && !result.loaded) void loadResult(result.resultId);
  };

  return (
    <Card padding="sm" data-testid={`result-card-${result.resultId}`}>
      <CardHeader
        title={result.tool ?? "Study result"}
        subtitle={<span className="font-mono">{result.resultId.slice(0, 16)}…</span>}
        icon={<FileBarChart className="w-4 h-4" />}
        action={<Badge variant="success">ready</Badge>}
      />
      <CardSection>
        <div className="flex items-center justify-end gap-2">
          <Button
            size="sm"
            variant="outline"
            loading={result.loading}
            disabled={result.loading}
            onClick={open}
            data-testid={`open-result-${result.resultId}`}
          >
            View
          </Button>
        </div>
      </CardSection>
    </Card>
  );
}
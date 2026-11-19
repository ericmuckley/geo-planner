export async function readRequestJson(request: Request, maxBytes: number) {
	const reader = request.body?.getReader();
	if (!reader) throw new Error("Missing body");
	const decoder = new TextDecoder();
	let bytes = 0;
	let body = "";
	try {
		while (true) {
			const chunk = await reader.read();
			if (chunk.done) break;
			bytes += chunk.value.byteLength;
			if (bytes > maxBytes) {
				await reader.cancel();
				throw new Error("Body too large");
			}
			body += decoder.decode(chunk.value, { stream: true });
		}
		return JSON.parse(body + decoder.decode());
	} finally {
		reader.releaseLock();
	}
}

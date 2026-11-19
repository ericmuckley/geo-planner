/** Small stage output must not advance Node's globally retained Buffer pool. */
export function disableHostBufferPooling() {
	// Scope this to a standalone verifier process, before its measured runtime loads.
	Buffer.poolSize = 0;
}

export function unpooledUtf8(text: string) {
	const buffer = Buffer.alloc(Buffer.byteLength(text));
	if (buffer.write(text) !== buffer.length)
		throw new Error("Incomplete UTF-8 host output");
	return buffer;
}

export function writeHostProgress(text: string) {
	return new Promise<void>((resolve, reject) => {
		process.stdout.write(unpooledUtf8(text), (error) => {
			if (error) reject(error);
			else resolve();
		});
	});
}

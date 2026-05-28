<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\Book;
use App\Models\BookFile;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Storage;

class BookFileController extends Controller
{
    public function index($bookId)
    {
        $book = Book::findOrFail($bookId);

        return response()->json($book->files);
    }

    public function store(Request $request, $bookId)
    {
        $request->validate([
            'file' => 'required|file|mimes:epub,pdf|max:51200',
        ]);

        $book = Book::findOrFail($bookId);

        $file = $request->file('file');
        $format = strtolower($file->getClientOriginalExtension());
        $path = "books/{$bookId}/" . $file->hashName();

        Storage::disk('s3')->put($path, file_get_contents($file->getRealPath()), 'private');

        $bookFile = $book->files()->create([
            'format'    => $format,
            'file_path' => $path,
            'file_size' => $file->getSize(),
        ]);

        return response()->json($bookFile, 201);
    }

    public function destroy($id)
    {
        $bookFile = BookFile::findOrFail($id);

        Storage::disk('s3')->delete($bookFile->file_path);
        $bookFile->delete();

        return response()->json(null, 204);
    }
}

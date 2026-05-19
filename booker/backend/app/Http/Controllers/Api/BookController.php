<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\Book;
use Illuminate\Http\Request;

class BookController extends Controller
{
    // GET /api/books
    public function index()
    {
        $books = Book::all();

    return response()->json([
        'data' => $books
    ]);
    }

    // GET /api/books/{id}
    public function show($id)
    {
        return Book::findOrFail($id);
    }

    // POST /api/books
    public function store(Request $request)
    {
        $validated = $request->validate([
            'title' => 'required|string|max:255',
            'author' => 'nullable|string|max:255',
            'description' => 'nullable|string',
            'isbn' => 'nullable|string|max:50',
            'language' => 'nullable|string|max:10',
            'cover_image_path' => 'nullable|string',
        ]);

        $book = Book::create($validated);

        return response()->json($book, 201);
    }

    // PUT /api/books/{id}
    public function update(Request $request, $id)
    {
        $book = Book::findOrFail($id);

        $validated = $request->validate([
            'title' => 'sometimes|string|max:255',
            'author' => 'nullable|string|max:255',
            'description' => 'nullable|string',
            'isbn' => 'nullable|string|max:50',
            'language' => 'nullable|string|max:10',
            'cover_image_path' => 'nullable|string',
        ]);

        $book->update($validated);

        return response()->json($book);
    }

    // DELETE /api/books/{id}
    public function destroy($id)
    {
        $book = Book::findOrFail($id);
        $book->delete();

        return response()->json(['message' => 'Book deleted']);
    }
}

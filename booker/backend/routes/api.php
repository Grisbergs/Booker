<?php

use Illuminate\Support\Facades\Route;
use App\Http\Controllers\Api\BookController;
use App\Http\Controllers\Api\BookFileController;

Route::get('/books', [BookController::class, 'index']);
Route::get('/books/{id}', [BookController::class, 'show']);
Route::post('/books', [BookController::class, 'store']);
Route::put('/books/{id}', [BookController::class, 'update']);
Route::delete('/books/{id}', [BookController::class, 'destroy']);

Route::get('/books/{bookId}/files', [BookFileController::class, 'index']);
Route::post('/books/{bookId}/files', [BookFileController::class, 'store']);
Route::delete('/book-files/{id}', [BookFileController::class, 'destroy']);

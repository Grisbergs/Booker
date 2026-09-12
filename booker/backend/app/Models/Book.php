<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class Book extends Model
{
    protected $fillable = [
        'title',
        'author',
        'description',
        'isbn',
        'language',
        'cover_image_path',
    ];

    public function files()
    {
        return $this->hasMany(BookFile::class);
    }
}
